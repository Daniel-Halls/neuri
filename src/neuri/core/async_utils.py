"""Asynchronous subprocess lifecycle and ephemeral event loop utilities.

Provides centralized helpers for reaping subprocesses, closing underlying
pipe transports before event loop shutdown, and executing coroutines safely
from synchronous threads without leaking BaseSubprocessTransport handles.
"""

import asyncio
import contextlib
import gc
from collections.abc import Coroutine
from concurrent.futures import ThreadPoolExecutor
from typing import Any


def close_subprocess_transport(
    process: asyncio.subprocess.Process | None,
) -> None:
    """Close subprocess pipe transports while the owning event loop is open.

    Parameters
    ------------
    process: asyncio.subprocess.Process | None
        Asyncio subprocess handle whose internal transport should be closed.

    Returns
    --------
        None: NoneType object
            Closes associated stdin writer and subprocess transport safely.
    """
    if process is None:
        return

    stdin_stream: Any = getattr(process, "stdin", None)
    if (
        isinstance(stdin_stream, asyncio.StreamWriter)
        and not stdin_stream.is_closing()
    ):
        with contextlib.suppress(Exception):
            stdin_stream.close()

    transport: Any = getattr(process, "_transport", None)
    if isinstance(transport, asyncio.BaseTransport):
        with contextlib.suppress(Exception):
            transport.close()


async def cleanup_subprocess(
    process: asyncio.subprocess.Process | None,
    wait_timeout: float = 2.0,
) -> None:
    """Terminate a subprocess if still running, reap it, and close transports.

    Parameters
    ------------
    process: asyncio.subprocess.Process | None
        Subprocess instance to clean up. Safe to pass None.
    wait_timeout: float
        Maximum seconds to wait for child reaping after kill. Defaults to 2.0.

    Returns
    --------
        None: NoneType object
            Reaps child process and closes its asyncio pipe transports.
    """
    if process is None:
        return

    try:
        if process.returncode is None:
            with contextlib.suppress(ProcessLookupError, OSError):
                process.kill()
            with contextlib.suppress(
                asyncio.TimeoutError,
                ProcessLookupError,
                OSError,
            ):
                await asyncio.wait_for(process.wait(), timeout=wait_timeout)
    finally:
        close_subprocess_transport(process)

    await asyncio.sleep(0)


async def drain_event_loop_tasks() -> None:
    """Cancel lingering tasks and drain transport callbacks before loop close.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Cancels orphaned tasks, collects unclosed transports, and yields.
    """
    current: asyncio.Task[Any] | None = asyncio.current_task()
    pending: list[asyncio.Task[Any]] = [
        task
        for task in asyncio.all_tasks()
        if task is not current and not task.done()
    ]
    for task in pending:
        task.cancel()
    if pending:
        with contextlib.suppress(Exception):
            await asyncio.gather(*pending, return_exceptions=True)

    gc.collect()
    await asyncio.sleep(0)


async def _execute_and_drain(coro: Coroutine[Any, Any, Any]) -> Any:
    """Run target coroutine and drain pending loop callbacks before teardown.

    Parameters
    ------------
    coro: Coroutine[Any, Any, Any]
        Coroutine to execute inside an ephemeral event loop.

    Returns
    --------
        Any: Any object
            Result produced by the awaited coroutine.
    """
    try:
        return await coro
    finally:
        await drain_event_loop_tasks()


def run_coro_cleanly(coro: Coroutine[Any, Any, Any]) -> Any:
    """Execute a coroutine synchronously with clean subprocess loop teardown.

    Parameters
    ------------
    coro: Coroutine[Any, Any, Any]
        Coroutine instance to execute to completion.

    Returns
    --------
        Any: Any object
            Result returned by the executed coroutine.
    """
    has_running_loop: bool = False
    try:
        asyncio.get_running_loop()
        has_running_loop = True
    except RuntimeError:
        has_running_loop = False

    wrapped: Coroutine[Any, Any, Any] = _execute_and_drain(coro)
    if has_running_loop:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, wrapped)
            return future.result()
    return asyncio.run(wrapped)
