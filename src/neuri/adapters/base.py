"""Vendor-agnostic abstract base harness adapter for Neuri.

Provides the canonical lifecycle contract for dispatching task envelopes to
command-line agent harnesses (e.g. Antigravity, OpenAI Codex CLI, Ollama),
normalizing streaming telemetry, handling circuit breakers, and returning
typed execution results.
"""

from abc import ABC, abstractmethod
import asyncio
from collections.abc import Callable
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import time
from typing import Any

from neuri.core.schemas import NeuriTaskEnvelope, NeuriTaskResult, TelemetryEvent
from neuri.core.telemetry import (
    CircuitBreakerTripped,
    NormalizedStreamResult,
    StreamEventNormalizer,
    TelemetryTap,
)


class HarnessExecutionError(Exception):
    """Exception raised when a harness subprocess fails or terminates abnormally.

    Parameters
    ------------
    message: str
        Explanatory error message detailing execution failure.
    exit_code: int
        Process exit code from harness execution. Defaults to 1.
    stderr: str | None
        Captured standard error output. Defaults to None.

    Returns
    --------
        HarnessExecutionError: HarnessExecutionError instance
            Constructed exception object.
    """

    def __init__(
        self, message: str, exit_code: int = 1, stderr: str | None = None
    ) -> None:
        """Initialize harness execution error.

        Parameters
        ------------
        message: str
            Descriptive error message.
        exit_code: int
            Process exit status code. Defaults to 1.
        stderr: str | None
            Standard error text from process. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes exception attributes.
        """
        super().__init__(message)
        self.message: str = message
        self.exit_code: int = exit_code
        self.stderr: str | None = stderr


class BaseHarnessAdapter(ABC):
    """Abstract base class for all external agent harness adapters.

    Parameters
    ------------
    None

    Returns
    --------
        BaseHarnessAdapter: BaseHarnessAdapter instance
            Constructed adapter base instance.
    """

    def __init__(self) -> None:
        """Initialize base adapter.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Initializes base state.
        """
        super().__init__()

    @property
    @abstractmethod
    def harness_id(self) -> str:
        """Canonical harness backend identifier (e.g. 'agy', 'codex', 'ollama').

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                Harness identifier.
        """
        pass

    @property
    @abstractmethod
    def executable_name(self) -> str:
        """Binary name for harness CLI on system PATH (e.g. 'agy', 'codex').

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                Executable binary name.
        """
        pass

    def is_available(self) -> bool:
        """Check if the harness binary is installed and executable on the host.

        Parameters
        ------------
        None

        Returns
        --------
            bool: boolean object
                True if executable is discovered on system PATH, False otherwise.
        """
        path_found: str | None = shutil.which(self.executable_name)
        available: bool = path_found is not None
        return available

    @abstractmethod
    def build_headless_command(
        self, envelope: NeuriTaskEnvelope
    ) -> list[str]:
        """Build command-line arguments for non-interactive streaming execution.

        Parameters
        ------------
        envelope: NeuriTaskEnvelope
            Task envelope containing instructions, budgets, and artifacts.

        Returns
        --------
            list[str]: list object
                Command-line arguments list starting with the executable binary.
        """
        pass

    @abstractmethod
    def build_interactive_command(
        self, envelope: NeuriTaskEnvelope
    ) -> list[str]:
        """Build command-line arguments for interactive escalation in terminal.

        Parameters
        ------------
        envelope: NeuriTaskEnvelope
            Task envelope requiring operator intervention.

        Returns
        --------
            list[str]: list object
                Command-line arguments list starting with the executable binary.
        """
        pass

    @abstractmethod
    def parse_stream_line(self, raw_line: str) -> NormalizedStreamResult:
        """Parse an incremental raw line of stdout into normalized events.

        Parameters
        ------------
        raw_line: str
            Raw text line or NDJSON line emitted by harness stdout.

        Returns
        --------
            NormalizedStreamResult: NormalizedStreamResult instance
                Extracted telemetry events and visible content deltas.
        """
        pass

    def build_environment(
        self, envelope: NeuriTaskEnvelope
    ) -> dict[str, str]:
        """Construct subprocess environment variables for the execution run.

        Parameters
        ------------
        envelope: NeuriTaskEnvelope
            Task envelope being executed.

        Returns
        --------
            dict[str, str]: dict object
                Environment variables dictionary for subprocess.
        """
        env: dict[str, str] = dict(os.environ)
        env["NEURI_NODE_ID"] = envelope.node_id
        env["NEURI_WORKFLOW_ID"] = envelope.workflow_id
        env["NEURI_HARNESS_ID"] = self.harness_id
        env["NEURI_AGENT_ROLE"] = envelope.agent_role
        return env

    async def execute(
        self,
        envelope: NeuriTaskEnvelope,
        on_event: Callable[[TelemetryEvent], None] | None = None,
        timeout_seconds: float = 600.0,
        working_dir: Path | None = None,
        blackboard: Any | None = None,
    ) -> NeuriTaskResult:
        """Execute task envelope asynchronously with streaming telemetry tapping.

        Parameters
        ------------
        envelope: NeuriTaskEnvelope
            Task envelope defining instructions, constraints, and artifacts.
        on_event: Callable[[TelemetryEvent], None] | None
            Optional callback invoked synchronously whenever a TelemetryEvent
            is emitted. Defaults to None.
        timeout_seconds: float
            Subprocess timeout in seconds. Defaults to 600.0 (10 minutes).
        working_dir: Path | None
            Working directory for subprocess execution. Defaults to None.
        blackboard: Any | None
            Optional Blackboard instance for state check-pointing.
            Defaults to None.

        Returns
        --------
            NeuriTaskResult: NeuriTaskResult instance
                Consolidated execution result capturing status, output, and cost.
        """
        if envelope.execution_mode == "interactive_pty":
            cmd: list[str] = self.build_interactive_command(envelope)
        else:
            cmd = self.build_headless_command(envelope)
        env: dict[str, str] = self.build_environment(envelope)
        cwd: str = str(working_dir) if working_dir is not None else os.getcwd()

        tap: TelemetryTap = TelemetryTap(
            workflow_id=envelope.workflow_id,
            node_id=envelope.node_id,
            harness_id=self.harness_id,
            max_node_tokens=envelope.max_tokens_budget,
            max_workflow_cost_usd=envelope.max_cost_usd,
            blackboard=blackboard,
        )

        accumulated_output: list[str] = []
        stderr_lines: list[str] = []
        exit_code: int = -1
        breaker_error: CircuitBreakerTripped | None = None

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=cwd,
            )

            stdout_task = asyncio.create_task(
                self._stream_stdout(
                    process=process,
                    tap=tap,
                    accumulated_output=accumulated_output,
                    on_event=on_event,
                )
            )
            stderr_task = asyncio.create_task(
                self._stream_stderr(
                    process=process,
                    stderr_lines=stderr_lines,
                )
            )

            await asyncio.wait_for(
                asyncio.gather(stdout_task, stderr_task, process.wait()),
                timeout=timeout_seconds,
            )
            exit_code = process.returncode if process.returncode is not None else 0
            breaker_error = stdout_task.result()

        except asyncio.TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            timeout_res: NeuriTaskResult = NeuriTaskResult(
                node_id=envelope.node_id,
                success=False,
                exit_code=-2,
                summary=(
                    f"Execution timed out after {timeout_seconds:.1f}s on "
                    f"harness '{self.harness_id}'"
                ),
                total_tokens=tap.get_total_tokens(),
                cost_usd=tap.get_cost_usd(),
                error_message=f"Timeout of {timeout_seconds}s exceeded",
                raw_output="".join(accumulated_output),
            )
            return timeout_res

        except FileNotFoundError:
            missing_res: NeuriTaskResult = NeuriTaskResult(
                node_id=envelope.node_id,
                success=False,
                exit_code=127,
                summary=(
                    f"Executable '{self.executable_name}' was not found on PATH"
                ),
                total_tokens=0,
                cost_usd=0.0,
                error_message=f"Binary not found: {self.executable_name}",
                raw_output="",
            )
            return missing_res

        except Exception as exc:
            err_res: NeuriTaskResult = NeuriTaskResult(
                node_id=envelope.node_id,
                success=False,
                exit_code=1,
                summary=f"Execution error on '{self.harness_id}': {exc}",
                total_tokens=tap.get_total_tokens(),
                cost_usd=tap.get_cost_usd(),
                error_message=str(exc),
                raw_output="".join(accumulated_output),
            )
            return err_res

        # If circuit breaker was tripped during streaming
        if breaker_error is not None:
            cb_res: NeuriTaskResult = NeuriTaskResult(
                node_id=envelope.node_id,
                success=False,
                exit_code=130,
                summary=f"Circuit breaker tripped: {breaker_error.reason}",
                total_tokens=tap.get_total_tokens(),
                cost_usd=tap.get_cost_usd(),
                error_message=breaker_error.reason,
                raw_output="".join(accumulated_output),
            )
            return cb_res

        success_flag: bool = exit_code == 0
        clean_text: str = tap.get_clean_text().strip()
        err_msg: str | None = "".join(stderr_lines) if not success_flag else None

        result: NeuriTaskResult = NeuriTaskResult(
            node_id=envelope.node_id,
            success=success_flag,
            exit_code=exit_code,
            summary=clean_text if clean_text else f"Exit code {exit_code}",
            total_tokens=tap.get_total_tokens(),
            cost_usd=tap.get_cost_usd(),
            error_message=err_msg,
            raw_output="".join(accumulated_output),
        )
        return result

    async def _stream_stdout(
        self,
        process: asyncio.subprocess.Process,
        tap: TelemetryTap,
        accumulated_output: list[str],
        on_event: Callable[[TelemetryEvent], None] | None = None,
    ) -> CircuitBreakerTripped | None:
        """Stream and process stdout lines from subprocess into TelemetryTap.

        Parameters
        ------------
        process: asyncio.subprocess.Process
            Running subprocess instance.
        tap: TelemetryTap
            Telemetry tap accumulator and circuit breaker monitor.
        accumulated_output: list[str]
            List accumulating raw stdout lines.
        on_event: Callable[[TelemetryEvent], None] | None
            Optional event emission callback. Defaults to None.

        Returns
        --------
            CircuitBreakerTripped | None: Exception or None
                Circuit breaker exception if tripped, None otherwise.
        """
        if process.stdout is None:
            return None

        while True:
            line_bytes: bytes = await process.stdout.readline()
            if not line_bytes:
                break
            raw_line: str = line_bytes.decode("utf-8", errors="replace")
            accumulated_output.append(raw_line)

            try:
                events: list[TelemetryEvent] = tap.process_chunk(raw_line)
                for ev in events:
                    if on_event is not None:
                        on_event(ev)
            except CircuitBreakerTripped as exc:
                try:
                    process.terminate()
                except ProcessLookupError:
                    pass
                return exc

        return None

    async def _stream_stderr(
        self,
        process: asyncio.subprocess.Process,
        stderr_lines: list[str],
    ) -> None:
        """Stream stderr lines from subprocess into accumulator list.

        Parameters
        ------------
        process: asyncio.subprocess.Process
            Running subprocess instance.
        stderr_lines: list[str]
            List accumulating raw stderr lines.

        Returns
        --------
            None: NoneType object
                Appends lines to accumulator.
        """
        if process.stderr is None:
            return

        while True:
            line_bytes: bytes = await process.stderr.readline()
            if not line_bytes:
                break
            stderr_lines.append(
                line_bytes.decode("utf-8", errors="replace")
            )


__all__: list[str] = [
    "BaseHarnessAdapter",
    "HarnessExecutionError",
]
