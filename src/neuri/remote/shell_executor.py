"""Local and remote shell command execution engine for Neuri.

Provides unified execution of shell commands on localhost (via asyncio
subprocesses) and remote machines (via SSHControlMasterPool), formatting
results with exit codes, execution duration, and stdout/stderr capture.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Any

from neuri.core.config import NeuriConfig
from neuri.remote.monitor import RemoteHostMonitor
from neuri.remote.ssh_pool import SSHControlMasterPool


@dataclass(frozen=True)
class ShellExecutionResult:
    """Encapsulates outcome of a local or remote shell command execution.

    Parameters
    ------------
    command: str
        The shell command that was executed.
    host: str
        The target host alias or 'localhost'.
    exit_code: int
        Return code from the process.
    stdout: str
        Standard output captured from process.
    stderr: str
        Standard error captured from process.
    duration_seconds: float
        Total execution wall-clock time in seconds.

    Returns
    --------
        ShellExecutionResult: ShellExecutionResult instance
            Constructed shell result model.
    """

    command: str
    host: str
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float


class ShellCommandExecutor:
    """Executes shell commands across local and remote compute hosts.

    Parameters
    ------------
    workspace_dir: Path | None
        Target local workspace directory for local command cwd. Defaults to None.
    ssh_pool: SSHControlMasterPool | None
        SSH connection pool for remote hosts. Defaults to None.

    Returns
    --------
        ShellCommandExecutor: ShellCommandExecutor instance
            Constructed shell command executor.
    """

    LOCAL_HOST_ALIASES: tuple[str, ...] = ("localhost", "local", "127.0.0.1")

    def __init__(
        self,
        workspace_dir: Path | None = None,
        ssh_pool: SSHControlMasterPool | None = None,
    ) -> None:
        """Initialize shell command executor with workspace and SSH pool.

        Parameters
        ------------
        workspace_dir: Path | None
            Working directory for local command execution. Defaults to None.
        ssh_pool: SSHControlMasterPool | None
            SSH connection pool for remote commands. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes executor instances.
        """
        self._workspace_dir: Path = (
            workspace_dir if workspace_dir is not None else Path.cwd()
        )
        self._ssh_pool: SSHControlMasterPool = (
            ssh_pool if ssh_pool is not None else SSHControlMasterPool()
        )

    def is_local(self, host: str) -> bool:
        """Check if target host represents the local machine.

        Parameters
        ------------
        host: str
            Host name or alias to evaluate.

        Returns
        --------
            bool: boolean object
                True if host is localhost alias, False otherwise.
        """
        is_loc: bool = host.lower().strip() in self.LOCAL_HOST_ALIASES
        return is_loc

    def get_available_hosts(
        self, config: NeuriConfig | None = None
    ) -> list[str]:
        """Discover list of all target hosts including localhost and remotes.

        Parameters
        ------------
        config: NeuriConfig | None
            Optional configuration model to inspect for project remote hosts.
            Defaults to None.

        Returns
        --------
        list[str]: list object
            Deduplicated list of available host aliases starting with localhost.
        """
        hosts: list[str] = ["localhost"]
        try:
            monitor: RemoteHostMonitor = RemoteHostMonitor()
            configured: list[str] = monitor.get_configured_hosts()
            for host in configured:
                if host not in hosts and host not in self.LOCAL_HOST_ALIASES:
                    hosts.append(host)
        except Exception:
            pass

        if config is not None:
            remote_hosts: list[Any] = getattr(config, "remote_hosts", []) or []
            for rh in remote_hosts:
                name: str = getattr(rh, "name", "")
                if (
                    name
                    and name not in hosts
                    and name not in self.LOCAL_HOST_ALIASES
                ):
                    hosts.append(name)

        return hosts

    async def warm_host(self, host: str) -> bool:
        """Pre-warm connection to a host if it is a remote target.

        Parameters
        ------------
        host: str
            Host name or alias to pre-warm.

        Returns
        --------
            bool: boolean object
                True if local or if remote connection is warm, False otherwise.
        """
        clean_host: str = host.strip() if host.strip() else "localhost"
        if self.is_local(clean_host):
            return True
        warmed: bool = await self._ssh_pool.warm_connection(clean_host)
        return warmed

    async def execute(
        self,
        command: str,
        host: str = "localhost",
        timeout_seconds: float = 120.0,
    ) -> ShellExecutionResult:
        """Execute command either locally or on remote host over SSH.

        Parameters
        ------------
        command: str
            Shell command string to execute.
        host: str
            Target machine alias ('localhost' or remote host).
            Defaults to 'localhost'.
        timeout_seconds: float
            Maximum execution timeout in seconds. Defaults to 120.0.

        Returns
        --------
            ShellExecutionResult: ShellExecutionResult instance
                Captured exit code, output streams, and timing metrics.
        """
        start_time: float = time.monotonic()
        clean_host: str = host.strip() if host.strip() else "localhost"

        if self.is_local(clean_host):
            res: ShellExecutionResult = await self._execute_local(
                command=command,
                host=clean_host,
                start_time=start_time,
                timeout_seconds=timeout_seconds,
            )
            return res

        res_remote: ShellExecutionResult = await self._execute_remote(
            command=command,
            host=clean_host,
            start_time=start_time,
            timeout_seconds=timeout_seconds,
        )
        return res_remote

    async def _execute_local(
        self,
        command: str,
        host: str,
        start_time: float,
        timeout_seconds: float,
    ) -> ShellExecutionResult:
        """Execute shell command on local operating system.

        Parameters
        ------------
        command: str
            Shell command string.
        host: str
            Local host alias.
        start_time: float
            Monotonic start timestamp.
        timeout_seconds: float
            Maximum execution timeout.

        Returns
        --------
            ShellExecutionResult: ShellExecutionResult instance
                Local execution outcome.
        """
        try:
            proc: asyncio.subprocess.Process = (
                await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(self._workspace_dir),
                )
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout_seconds
            )
            elapsed: float = time.monotonic() - start_time
            code: int = proc.returncode if proc.returncode is not None else 0
            stdout_text: str = stdout_bytes.decode("utf-8", errors="replace")
            stderr_text: str = stderr_bytes.decode("utf-8", errors="replace")
            return ShellExecutionResult(
                command=command,
                host=host,
                exit_code=code,
                stdout=stdout_text,
                stderr=stderr_text,
                duration_seconds=elapsed,
            )
        except asyncio.TimeoutError:
            elapsed = time.monotonic() - start_time
            return ShellExecutionResult(
                command=command,
                host=host,
                exit_code=-2,
                stdout="",
                stderr=f"Command timed out after {timeout_seconds:.1f}s",
                duration_seconds=elapsed,
            )
        except Exception as exc:
            elapsed = time.monotonic() - start_time
            return ShellExecutionResult(
                command=command,
                host=host,
                exit_code=-1,
                stdout="",
                stderr=f"Local execution failed: {exc}",
                duration_seconds=elapsed,
            )

    async def _execute_remote(
        self,
        command: str,
        host: str,
        start_time: float,
        timeout_seconds: float,
    ) -> ShellExecutionResult:
        """Execute shell command on remote machine via SSH pool.

        Parameters
        ------------
        command: str
            Remote shell command string.
        host: str
            Target SSH host alias.
        start_time: float
            Monotonic start timestamp.
        timeout_seconds: float
            Execution timeout in seconds.

        Returns
        --------
            ShellExecutionResult: ShellExecutionResult instance
                Remote execution outcome.
        """
        code, stdout_str, stderr_str = await self._ssh_pool.run_command(
            host=host,
            command=command,
            timeout_seconds=timeout_seconds,
        )
        elapsed: float = time.monotonic() - start_time
        return ShellExecutionResult(
            command=command,
            host=host,
            exit_code=code,
            stdout=stdout_str,
            stderr=stderr_str,
            duration_seconds=elapsed,
        )

    def format_markdown_card(self, result: ShellExecutionResult) -> str:
        """Format shell execution result into GitHub-flavored Markdown.

        Parameters
        ------------
        result: ShellExecutionResult
            Execution result model to format.

        Returns
        --------
            str: string object
                Renderable markdown report card.
        """
        status_badge: str = (
            "✓ Success"
            if result.exit_code == 0
            else f"✗ Exit Code: {result.exit_code}"
        )
        lines: list[str] = [
            f"### Shell Output: `{result.host}`",
            f"**Command:** `{result.command}`  ",
            f"**Status:** {status_badge}  │  "
            f"**Duration:** `{result.duration_seconds:.2f}s`\n",
        ]

        if result.stdout.strip():
            lines.append("```bash")
            lines.append(result.stdout.rstrip())
            lines.append("```\n")
        elif result.exit_code == 0 and not result.stderr.strip():
            lines.append("*(Command completed with no stdout output)*\n")

        if result.stderr.strip():
            lines.append("**Standard Error:**")
            lines.append("```")
            lines.append(result.stderr.rstrip())
            lines.append("```")

        md_output: str = "\n".join(lines)
        return md_output


__all__: list[str] = [
    "ShellCommandExecutor",
    "ShellExecutionResult",
]
