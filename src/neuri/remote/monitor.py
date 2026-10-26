"""Remote compute host and job monitoring fabric for Neuri.

Queries attached machines over persistent multiplexed SSH ControlMaster sockets,
aggregating machine health, Slurm queues, and active worker tasks.
"""

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
import tomllib

from neuri.remote.ssh_pool import SSHControlMasterPool
from neuri_worker.inspector import MachineInspector


class RemoteHostMonitor:
    """Monitors attached machines and remote compute jobs across SSH spokes.

    Parameters
    ------------
    ssh_pool: SSHControlMasterPool | None
        SSH connection pool instance. Defaults to None (auto-initialized).
    hosts_path: Path | None
        Path to ~/.neuri/hosts.toml registry. Defaults to None.

    Returns
    --------
        RemoteHostMonitor: RemoteHostMonitor instance
            Constructed remote host monitor instance.
    """

    def __init__(
        self,
        ssh_pool: SSHControlMasterPool | None = None,
        hosts_path: Path | None = None,
    ) -> None:
        """Initialize host monitor with connection pool and registry path.

        Parameters
        ------------
        ssh_pool: SSHControlMasterPool | None
            SSH connection pool. Defaults to None.
        hosts_path: Path | None
            Path to hosts.toml registry. Defaults to ~/.neuri/hosts.toml.

        Returns
        --------
            None: NoneType object
                Initializes monitor state.
        """
        self._ssh_pool: SSHControlMasterPool = (
            ssh_pool if ssh_pool is not None else SSHControlMasterPool()
        )
        self._hosts_path: Path = (
            hosts_path
            if hosts_path is not None
            else Path.home() / ".neuri" / "hosts.toml"
        )

    def get_configured_hosts(self) -> list[str]:
        """Read all host aliases registered in ~/.neuri/hosts.toml.

        Parameters
        ------------
        None

        Returns
        --------
            list[str]: list object
                List of registered host alias strings.
        """
        hosts: list[str] = []
        if not self._hosts_path.is_file():
            return hosts

        try:
            content: str = self._hosts_path.read_text(encoding="utf-8")
            data: dict[str, Any] = tomllib.loads(content)
            hosts_dict: dict[str, Any] = data.get("hosts", {})
            hosts = sorted(hosts_dict.keys())
        except Exception:
            hosts = []

        return hosts

    async def query_host(
        self, host: str, timeout_seconds: float = 6.0
    ) -> dict[str, Any]:
        """Query machine vitals and job queues for a single target host.

        Parameters
        ------------
        host: str
            Target SSH host alias or 'localhost'.
        timeout_seconds: float
            Execution timeout in seconds. Defaults to 6.0.

        Returns
        --------
            dict[str, Any]: dictionary object
                Normalized dictionary of host health, vitals, and jobs.
        """
        if host in ("localhost", "127.0.0.1"):
            inspector: MachineInspector = MachineInspector()
            local_res: dict[str, Any] = inspector.inspect_all()
            local_res["host"] = host
            local_res["online"] = True
            return local_res

        # Remote execution over multiplexed SSH
        cmd: str = (
            "python3 -m neuri_worker.inspector 2>/dev/null || "
            "python3 -c \"import os, socket, json; "
            "print(json.dumps({'hostname': socket.gethostname(), "
            "'load_avg': list(os.getloadavg()) if hasattr(os, 'getloadavg') "
            "else [0.0, 0.0, 0.0], 'cpu_count': os.cpu_count() or 1, "
            "'neuri_jobs': [], 'slurm_jobs': [], 'tmux_sessions': []}))\""
        )
        code, out_str, err_str = await self._ssh_pool.run_command(
            host, cmd, timeout_seconds=timeout_seconds
        )

        status_result: dict[str, Any] = {
            "host": host,
            "online": False,
            "hostname": host,
            "cpu_count": 0,
            "load_avg": [0.0, 0.0, 0.0],
            "neuri_jobs": [],
            "slurm_jobs": [],
            "tmux_sessions": [],
            "error": None,
            "inspected_at": datetime.now(timezone.utc).isoformat(),
        }

        if code == 0 and out_str.strip():
            for line in reversed(out_str.strip().splitlines()):
                clean_line: str = line.strip()
                if clean_line.startswith("{") and clean_line.endswith("}"):
                    try:
                        parsed: dict[str, Any] = json.loads(clean_line)
                        status_result["online"] = True
                        status_result["hostname"] = parsed.get("hostname", host)
                        status_result["cpu_count"] = parsed.get("cpu_count", 1)
                        status_result["load_avg"] = parsed.get(
                            "load_avg", [0.0, 0.0, 0.0]
                        )
                        status_result["neuri_jobs"] = parsed.get(
                            "neuri_jobs", []
                        )
                        status_result["slurm_jobs"] = parsed.get(
                            "slurm_jobs", []
                        )
                        status_result["tmux_sessions"] = parsed.get(
                            "tmux_sessions", []
                        )
                        return status_result
                    except (json.JSONDecodeError, ValueError):
                        pass

        status_result["error"] = err_str.strip() or f"Failed with exit code {code}"
        return status_result

    async def query_all_hosts(
        self,
        hosts: list[str] | None = None,
        timeout_seconds: float = 6.0,
    ) -> list[dict[str, Any]]:
        """Query all registered or specified hosts concurrently.

        Parameters
        ------------
        hosts: list[str] | None
            Optional explicit host list. Defaults to None (loads from registry).
        timeout_seconds: float
            Timeout per host query. Defaults to 6.0.

        Returns
        --------
            list[dict[str, Any]]: list object
                Aggregated list of host inspection results.
        """
        target_hosts: list[str] = (
            hosts if hosts is not None else self.get_configured_hosts()
        )
        if not target_hosts:
            return []

        coros = [
            self.query_host(h, timeout_seconds=timeout_seconds)
            for h in target_hosts
        ]
        results: list[dict[str, Any]] = await asyncio.gather(*coros)
        return results


__all__: list[str] = [
    "RemoteHostMonitor",
]
