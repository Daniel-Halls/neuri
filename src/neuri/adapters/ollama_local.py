"""Local Ollama agent harness adapter for Neuri.

Wraps the Ollama CLI for local offline LLM execution incurring zero USD cost.
"""

from typing import Any

from neuri.adapters.base import BaseHarnessAdapter
from neuri.core.schemas import NeuriTaskEnvelope
from neuri.core.telemetry import NormalizedStreamResult, StreamEventNormalizer


class OllamaLocalAdapter(BaseHarnessAdapter):
    """Harness adapter executing task envelopes via local Ollama models.

    Parameters
    ------------
    executable_path: str | None
        Optional explicit binary path to 'ollama'. Defaults to 'ollama'.
    default_model: str | None
        Optional default local model tag. If None, dynamically resolved from
        the underlying 'ollama list' output. Defaults to None.

    Returns
    --------
        OllamaLocalAdapter: OllamaLocalAdapter instance
            Constructed Ollama harness adapter.
    """

    HARNESS_ID: str = "ollama"
    EXECUTABLE_NAME: str = "ollama"

    def __init__(
        self,
        executable_path: str | None = None,
        default_model: str | None = None,
    ) -> None:
        """Initialize Ollama adapter with optional binary path and model.

        Parameters
        ------------
        executable_path: str | None
            Explicit path to ollama binary. Defaults to None ('ollama' on PATH).
        default_model: str | None
            Optional default Ollama model identifier. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes adapter state.
        """
        super().__init__()
        self._executable_path: str = (
            executable_path if executable_path is not None else self.EXECUTABLE_NAME
        )
        self._default_model: str | None = default_model
        self._normalizer: StreamEventNormalizer = StreamEventNormalizer(
            harness_id=self.HARNESS_ID
        )

    @property
    def harness_id(self) -> str:
        """Canonical harness identifier ('ollama').

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
        """Binary name on system PATH ('ollama').

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

    def _resolve_target_model(self, envelope: NeuriTaskEnvelope) -> str:
        """Resolve the target Ollama model dynamically without hardcoding.

        Parameters
        ------------
        envelope: NeuriTaskEnvelope
            Task envelope containing optional model override.

        Returns
        --------
            str: string object
                Target model identifier to pass to 'ollama run'.
        """
        if envelope.model:
            return envelope.model
        if self._default_model:
            return self._default_model
        available: list[str] = self.list_available_models()
        if available:
            return available[0]
        return ""

    def _compose_prompt(self, envelope: NeuriTaskEnvelope) -> str:
        """Compose full prompt string from task envelope.

        Parameters
        ------------
        envelope: NeuriTaskEnvelope
            Task envelope containing instruction, artifacts, and feedback.

        Returns
        --------
            str: string object
                Combined prompt text.
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
        return full_prompt

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
                Argument list for ollama subprocess invocation.
        """
        target_model: str = self._resolve_target_model(envelope)
        full_prompt: str = self._compose_prompt(envelope)
        cmd: list[str] = [
            self.executable_name,
            "run",
        ]
        if target_model:
            cmd.append(target_model)
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
                Argument list for interactive ollama execution.
        """
        target_model: str = self._resolve_target_model(envelope)
        cmd: list[str] = [
            self.executable_name,
            "run",
        ]
        if target_model:
            cmd.append(target_model)
        cmd.append(envelope.task_instruction)
        return cmd

    def parse_stream_line(self, raw_line: str) -> NormalizedStreamResult:
        """Parse raw stream line from ollama stdout into TelemetryEvents.

        Parameters
        ------------
        raw_line: str
            Raw text line from ollama.

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
        """Query real local models directly from the Ollama CLI.

        Parameters
        ------------
        None

        Returns
        --------
            list[str]: list object
                Models returned directly by the 'ollama list' command.
        """
        import subprocess

        models: list[str] = []
        try:
            res: subprocess.CompletedProcess[str] = subprocess.run(
                [self.executable_name, "list"],
                capture_output=True,
                text=True,
                timeout=10.0,
            )
            if res.returncode != 0:
                return models
            lines: list[str] = [
                ln.strip()
                for ln in res.stdout.splitlines()
                if ln.strip()
            ]
            for line in lines:
                tokens: list[str] = line.split()
                if not tokens or tokens[0].upper() == "NAME":
                    continue
                if tokens[0] not in models:
                    models.append(tokens[0])
        except (subprocess.SubprocessError, OSError, TimeoutError):
            pass
        return models


__all__: list[str] = [
    "OllamaLocalAdapter",
]
