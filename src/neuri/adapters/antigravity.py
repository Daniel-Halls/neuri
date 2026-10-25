"""Google Antigravity (agy) agent harness adapter for Neuri.

Wraps the Antigravity CLI (agy) for headless streaming NDJSON execution
(--output-format stream-json --mode auto -p) and interactive terminal escalation
(-i / --prompt-interactive).
"""

from pathlib import Path
from typing import Any

from neuri.adapters.base import BaseHarnessAdapter
from neuri.core.schemas import NeuriTaskEnvelope
from neuri.core.telemetry import NormalizedStreamResult, StreamEventNormalizer


class AntigravityAdapter(BaseHarnessAdapter):
    """Harness adapter executing task envelopes via Google Antigravity (agy).

    Parameters
    ------------
    executable_path: str | None
        Optional explicit binary path to 'agy'. Defaults to 'agy'.

    Returns
    --------
        AntigravityAdapter: AntigravityAdapter instance
            Constructed Antigravity harness adapter.
    """

    HARNESS_ID: str = "agy"
    EXECUTABLE_NAME: str = "agy"

    def __init__(self, executable_path: str | None = None) -> None:
        """Initialize Antigravity adapter with optional binary path.

        Parameters
        ------------
        executable_path: str | None
            Explicit path to agy binary. Defaults to None ('agy' on PATH).

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
        """Canonical harness identifier ('agy').

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
        """Binary name on system PATH ('agy').

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
                Argument list for agy subprocess invocation.
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
            "-p",
            full_prompt,
            "--output-format",
            "stream-json",
            "--mode",
            "auto",
        ]

        # Add skill directories if specified
        for skill_path in envelope.skill_paths:
            if Path(skill_path).is_dir():
                cmd.extend(["--add-dir", skill_path])

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
                Argument list for interactive agy execution.
        """
        cmd: list[str] = [
            self.executable_name,
            "-i",
            envelope.task_instruction,
        ]
        for skill_path in envelope.skill_paths:
            if Path(skill_path).is_dir():
                cmd.extend(["--add-dir", skill_path])
        return cmd

    def parse_stream_line(self, raw_line: str) -> NormalizedStreamResult:
        """Parse raw NDJSON stream line from agy stdout into TelemetryEvents.

        Parameters
        ------------
        raw_line: str
            Raw text line or NDJSON payload from agy.

        Returns
        --------
            NormalizedStreamResult: NormalizedStreamResult instance
                Parsed events and clean visible content.
        """
        result: NormalizedStreamResult = self._normalizer.normalize_chunk(
            raw_line
        )
        return result


__all__: list[str] = [
    "AntigravityAdapter",
]
