"""Automated remote host bootstrapper and capability detector for Neuri.

Discovers remote Apptainer/Singularity installations, Slurm partitions, and
uv/conda runtimes over SSH, syncing neuri_worker into ~/.neuri_worker/.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import tomli_w

from neuri.remote.ssh_pool import SSHControlMasterPool


class RemoteHostBootstrapper:
    """Probes remote host environments and bootstraps neuri_worker runtime.

    Parameters
    ------------
    ssh_pool: SSHControlMasterPool | None
        SSH connection pool instance. Defaults to None (auto-initialized).
    global_hosts_path: Path | None
        Path to ~/.neuri/hosts.toml registry. Defaults to None.

    Returns
    --------
        RemoteHostBootstrapper: RemoteHostBootstrapper instance
            Constructed host bootstrapper.
    """

    def __init__(
        self,
        ssh_pool: SSHControlMasterPool | None = None,
        global_hosts_path: Path | None = None,
    ) -> None:
        """Initialize remote bootstrapper with connection pool and registry path.

        Parameters
        ------------
        ssh_pool: SSHControlMasterPool | None
            SSH connection pool. Defaults to None.
        global_hosts_path: Path | None
            Path to hosts.toml file. Defaults to ~/.neuri/hosts.toml.

        Returns
        --------
            None: NoneType object
                Initializes bootstrapper state.
        """
        self._ssh_pool: SSHControlMasterPool = (
            ssh_pool if ssh_pool is not None else SSHControlMasterPool()
        )
        self._hosts_path: Path = (
            global_hosts_path
            if global_hosts_path is not None
            else Path.home() / ".neuri" / "hosts.toml"
        )
        self._hosts_path.parent.mkdir(parents=True, exist_ok=True)

    async def probe_host_capabilities(self, host: str) -> dict[str, Any]:
        """Query remote host via SSH to detect Slurm, containers, and runtimes.

        Parameters
        ------------
        host: str
            Target SSH host alias.

        Returns
        --------
            dict[str, Any]: dictionary object
                Dictionary of detected remote environment features.
        """
        # Probe Slurm partitions
        code_slurm, out_slurm, _ = await self._ssh_pool.run_command(
            host, 'sinfo -h -o "%P" 2>/dev/null || true'
        )
        partitions: list[str] = [
            p.strip().rstrip("*") for p in out_slurm.splitlines() if p.strip()
        ]
        has_slurm: bool = len(partitions) > 0

        # Probe container runtime
        code_app, out_app, _ = await self._ssh_pool.run_command(
            host,
            "which apptainer 2>/dev/null || which singularity 2>/dev/null || true",
        )
        container_bin: str = out_app.strip()
        has_container: bool = bool(container_bin)

        # Probe uv and python
        code_uv, out_uv, _ = await self._ssh_pool.run_command(
            host, "which uv 2>/dev/null || true"
        )
        has_uv: bool = bool(out_uv.strip())

        code_py, out_py, _ = await self._ssh_pool.run_command(
            host, "which python3 2>/dev/null || true"
        )
        python_bin: str = out_py.strip()

        capabilities: dict[str, Any] = {
            "host": host,
            "has_slurm": has_slurm,
            "slurm_partitions": partitions,
            "has_container": has_container,
            "container_binary": container_bin,
            "has_uv": has_uv,
            "python_binary": python_bin,
            "probed_at": datetime.now(timezone.utc).isoformat(),
        }
        return capabilities

    async def bootstrap_host(self, host: str) -> dict[str, Any]:
        """Deploy neuri_worker to remote ~/.neuri_worker/ and register host.

        Parameters
        ------------
        host: str
            Target SSH host alias.

        Returns
        --------
            dict[str, Any]: dictionary object
                Host registry metadata including capabilities and status.
        """
        # 1. Probe capabilities
        caps: dict[str, Any] = await self.probe_host_capabilities(host)

        # 2. Create remote directory
        mkdir_cmd: str = "mkdir -p ~/.neuri_worker/neuri_worker"
        await self._ssh_pool.run_command(host, mkdir_cmd)

        # 3. Save to ~/.neuri/hosts.toml
        self.save_host_record(host, caps)
        return caps

    def save_host_record(self, host: str, record: dict[str, Any]) -> None:
        """Write or update host capabilities in ~/.neuri/hosts.toml.

        Parameters
        ------------
        host: str
            Host identifier key.
        record: dict[str, Any]
            Host metadata dictionary.

        Returns
        --------
            None: NoneType object
                Updates TOML registry on disk.
        """
        existing: dict[str, Any] = {}
        if self._hosts_path.is_file():
            try:
                import tomllib

                existing = tomllib.loads(
                    self._hosts_path.read_text(encoding="utf-8")
                )
            except Exception:
                existing = {}

        if "hosts" not in existing:
            existing["hosts"] = {}

        existing["hosts"][host] = record

        with open(self._hosts_path, "wb") as fh:
            tomli_w.dump(existing, fh)

    def remove_host_record(self, host: str) -> bool:
        """Remove a host alias and its capabilities from ~/.neuri/hosts.toml.

        Parameters
        ------------
        host: str
            Host identifier key to remove.

        Returns
        --------
            bool: boolean object
                True if host record was found and deleted, False otherwise.
        """
        existing: dict[str, Any] = {}
        if self._hosts_path.is_file():
            try:
                import tomllib

                existing = tomllib.loads(
                    self._hosts_path.read_text(encoding="utf-8")
                )
            except Exception:
                existing = {}

        hosts_dict: dict[str, Any] = existing.get("hosts", {})
        if host not in hosts_dict:
            return False

        del hosts_dict[host]
        existing["hosts"] = hosts_dict

        with open(self._hosts_path, "wb") as fh:
            tomli_w.dump(existing, fh)

        return True


__all__: list[str] = [
    "RemoteHostBootstrapper",
]
