"""Persistent multiplexed SSH ControlMaster connection pool for Neuri.

Manages persistent SSH ControlMaster sockets, remote command execution, and
port tunnels across remote compute workstations and HPC login nodes.
"""

import asyncio
from pathlib import Path


class SSHControlMasterPool:
    """Manages persistent SSH ControlMaster sockets and command execution.

    Parameters
    ------------
    control_dir: Path | None
        Directory where SSH control sockets are stored. Defaults to ~/.ssh.

    Returns
    --------
        SSHControlMasterPool: SSHControlMasterPool instance
            Constructed SSH connection pool manager.
    """

    DEFAULT_CONTROL_PERSIST: str = "4h"

    def __init__(self, control_dir: Path | None = None) -> None:
        """Initialize SSH connection pool manager.

        Parameters
        ------------
        control_dir: Path | None
            Directory storing multiplexed control sockets. Defaults to ~/.ssh.

        Returns
        --------
            None: NoneType object
                Initializes control socket paths.
        """
        self._control_dir: Path = (
            control_dir if control_dir is not None else Path.home() / ".ssh"
        )
        try:
            self._control_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

    def get_control_path_pattern(self) -> str:
        """Return the ControlPath option pattern for OpenSSH.

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                Control socket path pattern using compact SHA1 hash (%C).
        """
        pattern: str = str(self._control_dir / "neuri_mux_%C")
        return pattern

    def build_ssh_args(self, host: str) -> list[str]:
        """Construct standard OpenSSH command options for multiplexed connection.

        Parameters
        ------------
        host: str
            Target SSH host alias or IP address.

        Returns
        --------
            list[str]: list object
                Base argument list for ssh invocation with low-latency flags.
        """
        args: list[str] = [
            "ssh",
            "-o",
            "ControlMaster=auto",
            "-o",
            f"ControlPath={self.get_control_path_pattern()}",
            "-o",
            f"ControlPersist={self.DEFAULT_CONTROL_PERSIST}",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "GSSAPIAuthentication=no",
            "-o",
            "ForwardX11=no",
            "-o",
            "ForwardAgent=no",
            "-o",
            "Compression=no",
            "-o",
            "IPQoS=lowdelay",
            "-o",
            "Ciphers=aes128-gcm@openssh.com,chacha20-poly1305@openssh.com",
            "-o",
            "ServerAliveInterval=30",
            "-o",
            "ServerAliveCountMax=3",
            host,
        ]
        return args

    async def warm_connection(
        self, host: str, timeout_seconds: float = 8.0
    ) -> bool:
        """Ensure a multiplexed master connection is established and warm.

        Checks if an active ControlMaster socket exists; if not, launches
        a non-blocking background master process to establish the connection
        in advance of interactive commands.

        Parameters
        ------------
        host: str
            Target SSH host alias or address.
        timeout_seconds: float
            Maximum seconds to wait for connection handshake. Defaults to 8.0.

        Returns
        --------
            bool: boolean object
                True if master connection is warm and ready, False otherwise.
        """
        # 1. Quick check if master is already running and responding
        check_cmd: list[str] = [
            "ssh",
            "-O",
            "check",
            "-o",
            f"ControlPath={self.get_control_path_pattern()}",
            host,
        ]
        try:
            proc_check: asyncio.subprocess.Process = (
                await asyncio.create_subprocess_exec(
                    *check_cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
            )
            await asyncio.wait_for(proc_check.wait(), timeout=1.5)
            if proc_check.returncode == 0:
                return True
        except Exception:
            pass

        # 2. Not running, establish master in background with -fN
        warm_args: list[str] = [
            "ssh",
            "-fN",
            "-o",
            "ControlMaster=yes",
            "-o",
            f"ControlPath={self.get_control_path_pattern()}",
            "-o",
            f"ControlPersist={self.DEFAULT_CONTROL_PERSIST}",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=5",
            "-o",
            "GSSAPIAuthentication=no",
            "-o",
            "ForwardX11=no",
            "-o",
            "ForwardAgent=no",
            "-o",
            "Compression=no",
            "-o",
            "IPQoS=lowdelay",
            "-o",
            "Ciphers=aes128-gcm@openssh.com,chacha20-poly1305@openssh.com",
            "-o",
            "ServerAliveInterval=30",
            "-o",
            "ServerAliveCountMax=3",
            host,
        ]
        try:
            proc_warm: asyncio.subprocess.Process = (
                await asyncio.create_subprocess_exec(
                    *warm_args,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
            )
            await asyncio.wait_for(proc_warm.wait(), timeout=timeout_seconds)
            is_warmed: bool = proc_warm.returncode == 0
            return is_warmed
        except Exception:
            return False

    async def run_command(
        self,
        host: str,
        command: list[str] | str,
        timeout_seconds: float = 60.0,
    ) -> tuple[int, str, str]:
        """Execute a command on the remote host over multiplexed SSH.

        Parameters
        ------------
        host: str
            Target SSH host alias.
        command: list[str] | str
            Command and arguments to execute remotely.
        timeout_seconds: float
            Execution timeout in seconds. Defaults to 60.0.

        Returns
        --------
            tuple[int, str, str]: tuple object
                Tuple of (exit_code, stdout_str, stderr_str).
        """
        base_ssh: list[str] = self.build_ssh_args(host)
        cmd_str: str = (
            " ".join(command) if isinstance(command, list) else command
        )
        full_cmd: list[str] = [*base_ssh, cmd_str]

        try:
            process: asyncio.subprocess.Process = (
                await asyncio.create_subprocess_exec(
                    *full_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=timeout_seconds
            )
            code: int = process.returncode if process.returncode is not None else 0
            out_str: str = stdout_bytes.decode("utf-8", errors="replace")
            err_str: str = stderr_bytes.decode("utf-8", errors="replace")
            return (code, out_str, err_str)
        except asyncio.TimeoutError:
            return (-2, "", f"SSH command timed out after {timeout_seconds}s")
        except Exception as exc:
            return (-1, "", f"SSH execution failed: {exc}")

    async def is_reachable(self, host: str) -> bool:
        """Check if target host is reachable over SSH within 5 seconds.

        Parameters
        ------------
        host: str
            Target SSH host alias.

        Returns
        --------
            bool: boolean object
                True if host is reachable and authenticated, False otherwise.
        """
        code, _, _ = await self.run_command(host, "echo 1", timeout_seconds=5.0)
        reachable: bool = code == 0
        return reachable

    def build_tunnel_args(
        self, host: str, local_port: int, remote_port: int
    ) -> list[str]:
        """Construct SSH port forwarding arguments.

        Parameters
        ------------
        host: str
            Target SSH host.
        local_port: int
            Local port to listen on.
        remote_port: int
            Remote port to forward to on localhost.

        Returns
        --------
            list[str]: list object
                Command line arguments for establishing background port tunnel.
        """
        tunnel_spec: str = f"{local_port}:localhost:{remote_port}"
        args: list[str] = [
            "ssh",
            "-N",
            "-L",
            tunnel_spec,
            "-o",
            "ControlMaster=auto",
            "-o",
            f"ControlPath={self.get_control_path_pattern()}",
            "-o",
            f"ControlPersist={self.DEFAULT_CONTROL_PERSIST}",
            "-o",
            "BatchMode=yes",
            "-o",
            "GSSAPIAuthentication=no",
            "-o",
            "IPQoS=lowdelay",
            host,
        ]
        return args


__all__: list[str] = [
    "SSHControlMasterPool",
]
