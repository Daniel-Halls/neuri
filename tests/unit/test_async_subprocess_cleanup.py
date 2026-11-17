"""Regression tests for async subprocess cleanup and event loop shutdown.

Ensures timed-out or completed subprocesses spawned across SSHControlMasterPool,
ShellCommandExecutor, PersistentShellSession, BaseHarnessAdapter, and
NeuriGUIHandler close pipe transports cleanly before ephemeral event loops exit.
"""

import asyncio
import gc
import sys
import warnings
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from neuri.adapters.base import BaseHarnessAdapter
from neuri.core.async_utils import cleanup_subprocess, run_coro_cleanly
from neuri.core.schemas import NeuriTaskEnvelope, NeuriTaskResult
from neuri.core.telemetry import NormalizedStreamResult
from neuri.gui.server import NeuriGUIHandler
from neuri.remote.shell_executor import PersistentShellSession
from neuri.remote.ssh_pool import SSHControlMasterPool


class SleepingHarnessAdapter(BaseHarnessAdapter):
    """Concrete minimal adapter executing a slow Python child for timeout tests.

    Parameters
    ------------
    None

    Returns
    --------
        SleepingHarnessAdapter: SleepingHarnessAdapter instance
            Constructed sleeping test adapter.
    """

    @property
    def harness_id(self) -> str:
        """Return synthetic test harness identifier.

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                Fixed identifier for test adapter.
        """
        return "test_sleep"

    @property
    def executable_name(self) -> str:
        """Return current Python executable path for portable subprocess tests.

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                Path to the active Python interpreter.
        """
        return sys.executable

    def build_headless_command(
        self, envelope: NeuriTaskEnvelope
    ) -> list[str]:
        """Return command that sleeps until terminated by adapter timeout.

        Parameters
        ------------
        envelope: NeuriTaskEnvelope
            Task envelope triggering execution.

        Returns
        --------
            list[str]: list object
                Command vector launching a sleeping Python child.
        """
        return [sys.executable, "-c", "import time; time.sleep(5)"]

    def build_interactive_command(
        self, envelope: NeuriTaskEnvelope
    ) -> list[str]:
        """Return interactive command fallback mirroring headless sleep.

        Parameters
        ------------
        envelope: NeuriTaskEnvelope
            Task envelope triggering execution.

        Returns
        --------
            list[str]: list object
                Command vector launching a sleeping Python child.
        """
        return self.build_headless_command(envelope)

    def parse_stream_line(self, raw_line: str) -> NormalizedStreamResult:
        """Parse an arbitrary stdout line cleanly.

        Parameters
        ------------
        raw_line: str
            Raw line read from stdout.

        Returns
        --------
            NormalizedStreamResult: NormalizedStreamResult instance
                Normalized delta wrapping raw text.
        """
        return NormalizedStreamResult(
            events=[],
            content_delta=raw_line,
            is_thinking=False,
        )


def _run_and_assert_no_loop_errors(
    action: Callable[[], Any],
) -> Any:
    """Execute a synchronous callable and verify no transport leak errors occur.

    Parameters
    ------------
    action: Callable[[], Any]
        Zero-argument callable running async loops or subprocess work.

    Returns
    --------
        Any: Any object
            Value returned by invoking action.
    """
    unraisable_errors: list[str] = []
    original_hook: Any = sys.unraisablehook

    def _capture_unraisable(args: Any) -> None:
        """Record any unraisable exception reported during garbage collection.

        Parameters
        ------------
        args: Any
            UnraisableHookArgs payload from Python runtime.

        Returns
        --------
            None: NoneType object
                Appends formatted exception description to captured list.
        """
        unraisable_errors.append(f"{args.exc_type}: {args.exc_value}")

    sys.unraisablehook = _capture_unraisable
    try:
        with warnings.catch_warnings(record=True) as recorded_warnings:
            warnings.simplefilter("always", ResourceWarning)
            result: Any = action()
            gc.collect()
            gc.collect()
    finally:
        sys.unraisablehook = original_hook

    assert unraisable_errors == []
    resource_warnings: list[str] = [
        str(warn.message)
        for warn in recorded_warnings
        if issubclass(warn.category, ResourceWarning)
    ]
    assert resource_warnings == []
    return result


def test_run_coro_cleanly_reaps_timed_out_subprocess_without_errors() -> None:
    """Timed-out local subprocess reaped with cleanup_subprocess leaves no leaks.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Verifies zero BaseSubprocessTransport errors after loop exit.
    """

    async def _spawn_and_timeout() -> int | None:
        """Spawn sleeping child, hit timeout, and clean up via helper.

        Parameters
        ------------
        None

        Returns
        --------
            int | None: int or None
                Child returncode after reaping.
        """
        proc: asyncio.subprocess.Process | None = None
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                "import time; time.sleep(5)",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(proc.communicate(), timeout=0.05)
        finally:
            await cleanup_subprocess(proc)
        return proc.returncode if proc is not None else None

    returncode: int | None = _run_and_assert_no_loop_errors(
        lambda: run_coro_cleanly(_spawn_and_timeout())
    )
    assert returncode is not None


async def test_run_coro_cleanly_from_running_loop_propagates_runtime_error() -> None:
    """Running a coroutine that raises RuntimeError inside active loop propagates.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Confirms inner RuntimeError is not caught and double-awaited.
    """

    async def _raise_runtime_error() -> None:
        """Raise an explicit RuntimeError inside coroutine body.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Always raises RuntimeError.
        """
        await asyncio.sleep(0)
        raise RuntimeError("inner coroutine failure")

    with pytest.raises(RuntimeError, match="inner coroutine failure"):
        run_coro_cleanly(_raise_runtime_error())


def test_ssh_pool_timeout_cleans_up_subprocess_transport(
    tmp_path: Path,
) -> None:
    """SSHControlMasterPool cleans subprocesses on timeout without loop errors.

    Parameters
    ------------
    tmp_path: Path
        Temporary directory fixture for synthetic control socket path.

    Returns
    --------
        None: NoneType object
            Verifies warm_connection and run_command_bytes leave zero leaks.
    """
    pool: SSHControlMasterPool = SSHControlMasterPool(control_dir=tmp_path)
    real_create_exec: Any = asyncio.create_subprocess_exec

    async def _fake_slow_ssh(
        *args: Any, **kwargs: Any
    ) -> asyncio.subprocess.Process:
        """Spawn a local sleeping Python process simulating stalled SSH.

        Parameters
        ------------
        *args: Any
            Original argv ignored in test double.
        **kwargs: Any
            Subprocess keyword options forwarded safely.

        Returns
        --------
            asyncio.subprocess.Process: Process instance
                Local slow child process handle.
        """
        proc: asyncio.subprocess.Process = await real_create_exec(
            sys.executable,
            "-c",
            "import time; time.sleep(5)",
            **kwargs,
        )
        return proc

    async def _exercise_timeouts() -> tuple[bool, int]:
        """Run warm_connection and run_command_bytes under short timeouts.

        Parameters
        ------------
        None

        Returns
        --------
            tuple[bool, int]: tuple object
                Results of (warmed, exit_code) on timeout.
        """
        with patch(
            "asyncio.create_subprocess_exec", side_effect=_fake_slow_ssh
        ):
            warmed: bool = await pool.warm_connection(
                "mock-host", timeout_seconds=0.05
            )
            code, _out, _err = await pool.run_command_bytes(
                "mock-host", "hostname", timeout_seconds=0.05
            )
            return (warmed, code)

    warmed_res, exit_code = _run_and_assert_no_loop_errors(
        lambda: run_coro_cleanly(_exercise_timeouts())
    )
    assert warmed_res is False
    assert exit_code == -2


def test_persistent_shell_session_timeout_and_close_cleans_transport(
    tmp_path: Path,
) -> None:
    """PersistentShellSession recovers from timeout and closes cleanly.

    Parameters
    ------------
    tmp_path: Path
        Temporary directory fixture used as shell working directory.

    Returns
    --------
        None: NoneType object
            Verifies timed-out persistent session leaves zero transport leaks.
    """

    async def _exercise_session() -> tuple[int, int, str]:
        """Trigger timeout, recover, and close PersistentShellSession cleanly.

        Parameters
        ------------
        None

        Returns
        --------
            tuple[int, int, str]: tuple object
                Tuple of (timeout_code, ok_code, ok_output).
        """
        session: PersistentShellSession = PersistentShellSession(
            host="localhost",
            is_local=True,
            workspace_dir=tmp_path,
            ssh_pool=SSHControlMasterPool(control_dir=tmp_path),
        )
        try:
            code_timeout, _out_t, _dur_t = await session.execute(
                "sleep 5", timeout_seconds=0.05
            )
            code_ok, out_ok, _dur_ok = await session.execute(
                "echo recovered", timeout_seconds=5.0
            )
            return (code_timeout, code_ok, out_ok)
        finally:
            await session.close()

    code_t, code_ok, output_ok = _run_and_assert_no_loop_errors(
        lambda: run_coro_cleanly(_exercise_session())
    )
    assert code_t == -2
    assert code_ok == 0
    assert "recovered" in output_ok


def test_base_harness_adapter_timeout_cleans_process_and_tasks() -> None:
    """BaseHarnessAdapter kills child, cancels readers, and closes transport.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Verifies adapter timeout inside ephemeral loop leaves no errors.
    """
    adapter: SleepingHarnessAdapter = SleepingHarnessAdapter()
    envelope: NeuriTaskEnvelope = NeuriTaskEnvelope(
        workflow_id="wf-timeout",
        node_id="node-timeout",
        agent_role="researcher",
        harness_id="test_sleep",
        execution_mode="headless_json",
        system_prompt="test prompt",
        task_instruction="sleep briefly",
        input_artifacts=[],
        skill_paths=[],
        max_tokens_budget=1000,
        max_cost_usd=1.0,
        attempt_number=1,
        max_retries=1,
    )

    result: NeuriTaskResult = _run_and_assert_no_loop_errors(
        lambda: run_coro_cleanly(
            adapter.execute(envelope=envelope, timeout_seconds=0.05)
        )
    )
    assert result.success is False
    assert result.exit_code == -2


def test_gui_handler_run_coro_sync_repeated_polls_leave_no_errors() -> None:
    """Repeated NeuriGUIHandler._run_coro_sync calls leave zero transport leaks.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Simulates consecutive /api/v1/machines polls terminating cleanly.
    """
    handler: NeuriGUIHandler = NeuriGUIHandler.__new__(NeuriGUIHandler)

    def _poll_once() -> int | None:
        """Execute a short subprocess coroutine via NeuriGUIHandler._run_coro_sync.

        Parameters
        ------------
        None

        Returns
        --------
            int | None: int or None
                Exit code from executed child command.
        """

        async def _quick_subproc() -> int | None:
            """Run a fast Python subprocess inside handler event loop.

            Parameters
            ------------
            None

            Returns
            --------
                int | None: int or None
                    Process exit code.
            """
            proc: asyncio.subprocess.Process | None = None
            try:
                proc = await asyncio.create_subprocess_exec(
                    sys.executable,
                    "-c",
                    "print('ok')",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(proc.communicate(), timeout=2.0)
                return proc.returncode
            finally:
                await cleanup_subprocess(proc)

        coro: Coroutine[Any, Any, int | None] = _quick_subproc()
        poll_code: int | None = handler._run_coro_sync(coro)
        return poll_code

    def _run_multiple_polls() -> list[int | None]:
        """Run three consecutive machine-style synchronous polls.

        Parameters
        ------------
        None

        Returns
        --------
            list[int | None]: list object
                Exit codes for each poll cycle.
        """
        return [_poll_once(), _poll_once(), _poll_once()]

    codes: list[int | None] = _run_and_assert_no_loop_errors(_run_multiple_polls)
    assert codes == [0, 0, 0]
