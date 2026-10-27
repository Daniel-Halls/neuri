"""Local and remote shell command execution engine for Neuri.

Provides unified execution of shell commands on localhost (via asyncio
subprocesses) and remote machines (via SSHControlMasterPool), formatting
results with exit codes, execution duration, and stdout/stderr capture.
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
import time
from typing import Any
import uuid

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


class PersistentShellSession:
    """Manages an active, long-lived shell session on a local or remote host.

    Eliminates per-command SSH handshake, PAM session initialization, and shell
    startup overhead by streaming commands into an already-running shell process.

    Parameters
    ------------
    host: str
        Target host alias or 'localhost'.
    is_local: bool
        Whether this session runs on the local operating system.
    workspace_dir: Path
        Local working directory for the process.
    ssh_pool: SSHControlMasterPool
        SSH pool used to construct multiplexed SSH arguments for remote hosts.

    Returns
    --------
        PersistentShellSession: PersistentShellSession instance
            Constructed persistent shell session controller.
    """

    def __init__(
        self,
        host: str,
        is_local: bool,
        workspace_dir: Path,
        ssh_pool: SSHControlMasterPool,
    ) -> None:
        """Initialize persistent shell session state.

        Parameters
        ------------
        host: str
            Target host alias.
        is_local: bool
            Whether host is localhost.
        workspace_dir: Path
            Workspace directory for local cwd.
        ssh_pool: SSHControlMasterPool
            SSH connection pool.

        Returns
        --------
            None: NoneType object
                Initializes instance properties.
        """
        self._host: str = host
        self._is_local: bool = is_local
        self._workspace_dir: Path = workspace_dir
        self._ssh_pool: SSHControlMasterPool = ssh_pool
        self._process: asyncio.subprocess.Process | None = None
        self._lock: asyncio.Lock = asyncio.Lock()

    def is_alive(self) -> bool:
        """Check whether the underlying shell subprocess is running.

        Parameters
        ------------
        None

        Returns
        --------
            bool: boolean object
                True if process exists and has not terminated, False otherwise.
        """
        alive: bool = (
            self._process is not None and self._process.returncode is None
        )
        return alive

    async def start(self) -> bool:
        """Start the persistent shell process if not already running.

        Parameters
        ------------
        None

        Returns
        --------
            bool: boolean object
                True if shell process started successfully, False on error.
        """
        if self.is_alive():
            return True

        try:
            if self._is_local:
                cmd_args: list[str] = ["/bin/bash"]
                cwd_path: str | None = str(self._workspace_dir)
            else:
                ssh_args: list[str] = self._ssh_pool.build_ssh_args(self._host)
                cmd_args = [*ssh_args, "bash || sh"]
                cwd_path = None

            self._process = await asyncio.create_subprocess_exec(
                *cmd_args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=cwd_path,
            )
            return True
        except Exception:
            self._process = None
            return False

    async def execute(
        self, command: str, timeout_seconds: float = 60.0
    ) -> tuple[int, str, float]:
        """Execute command in the persistent shell and stream results.

        Parameters
        ------------
        command: str
            Shell command to evaluate.
        timeout_seconds: float
            Maximum seconds to wait for execution to complete. Defaults to 60.0.

        Returns
        --------
            tuple[int, str, float]: tuple object
                Tuple containing exit code, stdout/stderr output, and elapsed time.
        """
        async with self._lock:
            if not self.is_alive():
                started: bool = await self.start()
                if (
                    not started
                    or self._process is None
                    or self._process.stdin is None
                ):
                    return (-1, "Failed to start persistent shell session", 0.0)

            start_t: float = time.monotonic()
            delim: str = f"__NEURI_END_{uuid.uuid4().hex[:10]}__"
            script: str = (
                f"{{ {command} ; }} ; printf \"{delim}:%d\\n\" \"$?\"\n"
            )

            try:
                self._process.stdin.write(script.encode("utf-8"))
                await self._process.stdin.drain()

                lines: list[str] = []
                exit_code: int = 0

                while True:
                    if self._process.stdout is None:
                        break
                    raw_line: bytes = await asyncio.wait_for(
                        self._process.stdout.readline(), timeout=timeout_seconds
                    )
                    if not raw_line:
                        # Subprocess terminated before marker (e.g. 'exit 42')
                        await self._process.wait()
                        if self._process.returncode is not None:
                            exit_code = self._process.returncode
                        self._process = None
                        break
                    decoded: str = raw_line.decode("utf-8", errors="replace")
                    if delim in decoded:
                        pos: int = decoded.find(delim)
                        status_str: str = decoded[pos + len(delim) :].strip()
                        if status_str.startswith(":"):
                            try:
                                exit_code = int(status_str[1:])
                            except ValueError:
                                exit_code = -1
                        break
                    lines.append(decoded)

                elapsed_t: float = time.monotonic() - start_t
                output_str: str = "".join(lines).strip()
                return (exit_code, output_str, elapsed_t)

            except asyncio.TimeoutError:
                elapsed_t = time.monotonic() - start_t
                if self._process is not None:
                    try:
                        self._process.kill()
                    except Exception:
                        pass
                    self._process = None
                return (
                    -2,
                    f"Command timed out after {timeout_seconds:.1f}s",
                    elapsed_t,
                )

            except Exception as exc:
                elapsed_t = time.monotonic() - start_t
                if self._process is not None:
                    try:
                        self._process.kill()
                    except Exception:
                        pass
                    self._process = None
                return (-1, f"Session error: {exc}", elapsed_t)

    async def close(self) -> None:
        """Close the persistent shell process and free process handles.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Terminates subprocess cleanly.
        """
        if self._process is not None and self._process.returncode is None:
            try:
                if self._process.stdin is not None:
                    self._process.stdin.close()
                await asyncio.wait_for(self._process.wait(), timeout=1.0)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
        self._process = None


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
        self._persistent_sessions: dict[str, PersistentShellSession] = {}

    def _get_or_create_session(
        self, host: str, is_local: bool
    ) -> PersistentShellSession:
        """Retrieve existing persistent session or initialize a new one.

        Parameters
        ------------
        host: str
            Target host alias.
        is_local: bool
            Whether host is local.

        Returns
        --------
            PersistentShellSession: PersistentShellSession instance
                Active or new session controller.
        """
        if host not in self._persistent_sessions:
            self._persistent_sessions[host] = PersistentShellSession(
                host=host,
                is_local=is_local,
                workspace_dir=self._workspace_dir,
                ssh_pool=self._ssh_pool,
            )
        session: PersistentShellSession = self._persistent_sessions[host]
        return session

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
        """Pre-warm connection and interactive shell session to a host.

        Parameters
        ------------
        host: str
            Host name or alias to pre-warm.

        Returns
        --------
            bool: boolean object
                True if host connection and session are ready, False otherwise.
        """
        clean_host: str = host.strip() if host.strip() else "localhost"
        is_loc: bool = self.is_local(clean_host)
        if is_loc:
            local_session: PersistentShellSession = (
                self._get_or_create_session(clean_host, is_loc)
            )
            local_warmed: bool = await local_session.start()
            return local_warmed

        ssh_warmed: bool = await self._ssh_pool.warm_connection(clean_host)
        if ssh_warmed:
            remote_session: PersistentShellSession = (
                self._get_or_create_session(clean_host, is_loc)
            )
            try:
                await remote_session.start()
            except Exception:
                pass
        return ssh_warmed

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
        clean_host: str = host.strip() if host.strip() else "localhost"
        is_loc: bool = self.is_local(clean_host)

        session: PersistentShellSession = self._get_or_create_session(
            clean_host, is_loc
        )
        try:
            code, out_str, elapsed = await session.execute(
                command=command, timeout_seconds=timeout_seconds
            )
            if (
                code != -1
                or "Failed to start persistent shell session" not in out_str
            ):
                stdout_res: str = out_str if code >= 0 else ""
                stderr_res: str = out_str if code != 0 else ""
                return ShellExecutionResult(
                    command=command,
                    host=clean_host,
                    exit_code=code,
                    stdout=stdout_res,
                    stderr=stderr_res,
                    duration_seconds=elapsed,
                )
        except Exception:
            pass

        start_time: float = time.monotonic()
        if is_loc:
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
            ""
            if result.exit_code == 0
            else f"ERROR: Exit Code: {result.exit_code}"
        )
        lines: list[str] = [
            f"### Machine: `{result.host}`{status_badge}\n",
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

    async def close_all(self) -> None:
        """Close all active persistent shell sessions cleanly.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Closes all managed subprocesses.
        """
        for sess in self._persistent_sessions.values():
            await sess.close()
        self._persistent_sessions.clear()


__all__: list[str] = [
    "PersistentShellSession",
    "ShellCommandExecutor",
    "ShellExecutionResult",
]
