"""OpenClaw CLI agent harness adapter for Neuri.

Wraps the OpenClaw CLI for headless streaming execution and interactive
terminal escalation.
"""

from typing import Any

from neuri.adapters.base import BaseHarnessAdapter
from neuri.core.schemas import NeuriTaskEnvelope
from neuri.core.telemetry import NormalizedStreamResult, StreamEventNormalizer


class OpenClawAdapter(BaseHarnessAdapter):
    """Harness adapter executing task envelopes via OpenClaw CLI.

    Parameters
    ------------
    executable_path: str | None
        Optional explicit binary path to 'openclaw'. Defaults to 'openclaw'.

    Returns
    --------
        OpenClawAdapter: OpenClawAdapter instance
            Constructed OpenClaw harness adapter.
    """

    HARNESS_ID: str = "openclaw"
    EXECUTABLE_NAME: str = "openclaw"

    def __init__(self, executable_path: str | None = None) -> None:
        """Initialize OpenClaw adapter with optional binary path.

        Parameters
        ------------
        executable_path: str | None
            Explicit path to openclaw binary. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes adapter state.
        """
        super().__init__()
        self._executable_path: str = (
            executable_path if executable_path is not None else self.EXECUTABLE_NAME
        )
        self._normalizer: StreamEventNormalizer = StreamEventNormalizer(
            harness_id=self.HARNESS_ID
        )

    @property
    def harness_id(self) -> str:
        """Canonical harness identifier ('openclaw').

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                Harness ID string.
        """
        h_id: str = self.HARNESS_ID
        return h_id

    @property
    def executable_name(self) -> str:
        """Binary name on system PATH ('openclaw').

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                Executable binary name.
        """
        name: str = self._executable_path
        return name

    def build_headless_command(
        self, envelope: NeuriTaskEnvelope
    ) -> list[str]:
        """Construct command-line arguments for headless streaming execution.

        Parameters
        ------------
        envelope: NeuriTaskEnvelope
            Task envelope containing instruction, artifacts, and constraints.

        Returns
        --------
            list[str]: list object
                Argument list for openclaw subprocess invocation.
        """
        prompt_parts: list[str] = []
        if envelope.system_prompt:
            prompt_parts.append(f"System: {envelope.system_prompt}")
        if envelope.input_artifacts:
            art_descriptions: list[str] = [
                f"- {art.artifact_id}: {art.uri} (modality: {art.modality}, "
                f"space: {art.space or 'native'})"
                for art in envelope.input_artifacts
            ]
            prompt_parts.append(
                "Input Artifacts:\n" + "\n".join(art_descriptions)
            )
        if envelope.diagnostic_feedback:
            prompt_parts.append(
                f"Previous Attempt Feedback: {envelope.diagnostic_feedback}"
            )
        prompt_parts.append(f"Task Instruction:\n{envelope.task_instruction}")
        full_prompt: str = "\n\n".join(prompt_parts)

        cmd: list[str] = [
            self.executable_name,
            "agent",
            "--local",
            "--json",
        ]
        if envelope.model:
            cmd.extend(["--model", envelope.model])
        cmd.extend(["--message", full_prompt])
        return cmd

    def build_interactive_command(
        self, envelope: NeuriTaskEnvelope
    ) -> list[str]:
        """Construct command-line arguments for interactive escalation.

        Parameters
        ------------
        envelope: NeuriTaskEnvelope
            Task envelope requiring operator intervention.

        Returns
        --------
            list[str]: list object
                Argument list for interactive openclaw execution.
        """
        cmd: list[str] = [
            self.executable_name,
            "agent",
            "--local",
        ]
        if envelope.model:
            cmd.extend(["--model", envelope.model])
        cmd.extend(["--message", envelope.task_instruction])
        return cmd

    def parse_stream_line(self, raw_line: str) -> NormalizedStreamResult:
        """Parse raw stream line from openclaw stdout into TelemetryEvents.

        Parameters
        ------------
        raw_line: str
            Raw text line or JSON payload from openclaw.

        Returns
        --------
            NormalizedStreamResult: NormalizedStreamResult instance
                Parsed events and clean visible content.
        """
        result: NormalizedStreamResult = self._normalizer.normalize_chunk(
            raw_line
        )
        return result

    def _parse_models_stdout(
        self, stdout_text: str, models: list[str]
    ) -> None:
        """Extract model identifiers from OpenClaw CLI stdout.

        Parameters
        ------------
        stdout_text: str
            Captured stdout from 'openclaw models list' or 'openclaw models'.
        models: list[str]
            Target list to append unique discovered model identifiers.

        Returns
        --------
            None: NoneType object
                Appends discovered models in place.
        """
        header_seen: bool = False
        for raw_line in stdout_text.splitlines():
            line: str = raw_line.strip()
            if "Model" in line and "Input" in line:
                header_seen = True
                continue
            if line.startswith("Default") and ":" in line:
                candidate_default: str = line.split(":", 1)[1].strip()
                if (
                    candidate_default
                    and candidate_default != "-"
                    and candidate_default not in models
                ):
                    models.append(candidate_default)
            elif header_seen and line:
                tokens: list[str] = line.split()
                if tokens and not tokens[0].startswith("Config"):
                    if tokens[0] not in models:
                        models.append(tokens[0])

    def _read_config_models(self, models: list[str]) -> None:
        """Read configured models from ~/.openclaw/openclaw.json if present.

        Parameters
        ------------
        models: list[str]
            Target list to append unique discovered model identifiers.

        Returns
        --------
            None: NoneType object
                Appends configured OpenClaw models in place.
        """
        import json
        from pathlib import Path

        cfg_file: Path = Path.home() / ".openclaw" / "openclaw.json"
        if not cfg_file.is_file():
            return
        try:
            data: dict[str, Any] = json.loads(
                cfg_file.read_text(encoding="utf-8")
            )
            defaults: dict[str, Any] = (
                data.get("agents", {}).get("defaults", {})
                if isinstance(data.get("agents"), dict)
                else {}
            )
            primary: Any = (
                defaults.get("model", {}).get("primary")
                if isinstance(defaults.get("model"), dict)
                else None
            )
            if isinstance(primary, str) and primary and primary not in models:
                models.append(primary)

            providers: dict[str, Any] = (
                data.get("models", {}).get("providers", {})
                if isinstance(data.get("models"), dict)
                else {}
            )
            for prov_id, prov_cfg in providers.items():
                if not isinstance(prov_cfg, dict):
                    continue
                prov_models: Any = prov_cfg.get("models", [])
                if isinstance(prov_models, list):
                    for m_entry in prov_models:
                        if isinstance(m_entry, dict) and m_entry.get("id"):
                            m_id: str = f"{prov_id}/{m_entry['id']}"
                            if m_id not in models:
                                models.append(m_id)
        except Exception:
            pass

    def list_available_models(self) -> list[str]:
        """Query real available models directly from the OpenClaw CLI.

        Parameters
        ------------
        None

        Returns
        --------
            list[str]: list object
                Models returned by 'openclaw models list' and OpenClaw config.
        """
        import subprocess

        models: list[str] = []
        try:
            res: subprocess.CompletedProcess[str] = subprocess.run(
                [self.executable_name, "models", "list"],
                capture_output=True,
                text=True,
                timeout=15.0,
            )
            if res.returncode == 0 and res.stdout.strip():
                self._parse_models_stdout(res.stdout, models)
            else:
                res_fallback: subprocess.CompletedProcess[str] = (
                    subprocess.run(
                        [self.executable_name, "models"],
                        capture_output=True,
                        text=True,
                        timeout=15.0,
                    )
                )
                if res_fallback.returncode == 0:
                    self._parse_models_stdout(res_fallback.stdout, models)
        except (subprocess.SubprocessError, OSError, TimeoutError):
            pass

        if self.is_available():
            self._read_config_models(models)

        return models


__all__: list[str] = [
    "OpenClawAdapter",
]
