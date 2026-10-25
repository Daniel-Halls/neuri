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
        cmd: list[str] = [
            self.executable_name,
            "--headless",
            "--stream-json",
            "--prompt",
            envelope.task_instruction,
        ]
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
            "--prompt",
            envelope.task_instruction,
        ]
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


__all__: list[str] = [
    "OpenClawAdapter",
]
