"""OpenAI Codex CLI agent harness adapter for Neuri.

Wraps the OpenAI Codex CLI (codex) for headless streaming JSON execution
(codex exec --json) and interactive terminal escalation (codex).
"""

from pathlib import Path
from typing import Any

from neuri.adapters.base import BaseHarnessAdapter
from neuri.core.schemas import NeuriTaskEnvelope
from neuri.core.telemetry import NormalizedStreamResult, StreamEventNormalizer


class CodexAdapter(BaseHarnessAdapter):
    """Harness adapter executing task envelopes via OpenAI Codex CLI (codex).

    Parameters
    ------------
    executable_path: str | None
        Optional explicit binary path to 'codex'. Defaults to 'codex'.

    Returns
    --------
        CodexAdapter: CodexAdapter instance
            Constructed Codex harness adapter.
    """

    HARNESS_ID: str = "codex"
    EXECUTABLE_NAME: str = "codex"

    def __init__(self, executable_path: str | None = None) -> None:
        """Initialize Codex adapter with optional binary path.

        Parameters
        ------------
        executable_path: str | None
            Explicit path to codex binary. Defaults to None ('codex' on PATH).

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
        """Canonical harness identifier ('codex').

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
        """Binary name on system PATH ('codex').

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
                Argument list for codex subprocess invocation.
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
            "exec",
            "--json",
        ]
        if envelope.model:
            cmd.extend(["--model", envelope.model])
        cmd.append(full_prompt)
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
                Argument list for interactive codex execution.
        """
        cmd: list[str] = [
            self.executable_name,
        ]
        if envelope.model:
            cmd.extend(["--model", envelope.model])
        cmd.append(envelope.task_instruction)
        return cmd

    def parse_stream_line(self, raw_line: str) -> NormalizedStreamResult:
        """Parse raw JSONL stream line from codex stdout into TelemetryEvents.

        Parameters
        ------------
        raw_line: str
            Raw text line or JSONL payload from codex.

        Returns
        --------
            NormalizedStreamResult: NormalizedStreamResult instance
                Parsed events and clean visible content.
        """
        result: NormalizedStreamResult = self._normalizer.normalize_chunk(
            raw_line
        )
        return result

    def list_available_models(self) -> list[str]:
        """Query real available models directly from the Codex CLI.

        Parameters
        ------------
        None

        Returns
        --------
            list[str]: list object
                Models returned directly by the 'codex models' command.
        """
        import subprocess

        models: list[str] = []
        try:
            res: subprocess.CompletedProcess[str] = subprocess.run(
                [self.executable_name, "models"],
                capture_output=True,
                text=True,
                timeout=10.0,
            )
            if res.returncode != 0:
                return models
            for raw_line in res.stdout.splitlines():
                line: str = raw_line.strip()
                if line and not line.startswith("="):
                    tokens: list[str] = line.split()
                    if tokens:
                        models.append(tokens[0])
        except (subprocess.SubprocessError, OSError, TimeoutError):
            pass
        return models


__all__: list[str] = [
    "CodexAdapter",
]
