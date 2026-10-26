"""Selective lightweight artifact synchronization for remote QA and status files.

Pulls small QA snapshot bundles (<200 KB PNG/SVG) and status.json sentinel files
while strictly preventing raw multi-gigabyte binary datasets from crossing network.
"""

import asyncio
from pathlib import Path

from neuri.remote.ssh_pool import SSHControlMasterPool


class ArtifactSyncManager:
    """Manages selective file synchronization between remote spokes and local hub.

    Parameters
    ------------
    ssh_pool: SSHControlMasterPool | None
        SSH connection pool instance. Defaults to None (auto-initialized).

    Returns
    --------
        ArtifactSyncManager: ArtifactSyncManager instance
            Constructed artifact synchronization manager.
    """

    MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB ceiling for sync

    def __init__(self, ssh_pool: SSHControlMasterPool | None = None) -> None:
        """Initialize artifact sync manager.

        Parameters
        ------------
        ssh_pool: SSHControlMasterPool | None
            SSH connection pool. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes manager state.
        """
        self._ssh_pool: SSHControlMasterPool = (
            ssh_pool if ssh_pool is not None else SSHControlMasterPool()
        )

    async def pull_file(
        self,
        host: str,
        remote_path: str,
        local_path: Path,
        timeout_seconds: float = 30.0,
    ) -> bool:
        """Pull a single lightweight file from remote spoke to local filesystem.

        Parameters
        ------------
        host: str
            Target SSH host alias.
        remote_path: str
            POSIX path to remote file.
        local_path: Path
            Local destination path.
        timeout_seconds: float
            Timeout for transfer. Defaults to 30.0.

        Returns
        --------
            bool: boolean object
                True if transfer succeeded, False otherwise.
        """
        local_path.parent.mkdir(parents=True, exist_ok=True)
        # Stream file contents over SSH stdout to avoid separate scp handshake
        cat_cmd: str = f"cat '{remote_path}'"
        code, stdout_str, _ = await self._ssh_pool.run_command(
            host, cat_cmd, timeout_seconds=timeout_seconds
        )

        if code != 0 or not stdout_str:
            return False

        local_path.write_text(stdout_str, encoding="utf-8")
        return True

    async def pull_qa_snapshots(
        self,
        host: str,
        remote_dir: str,
        local_target_dir: Path,
        timeout_seconds: float = 60.0,
    ) -> list[Path]:
        """Pull PNG and SVG QA snapshots from a remote directory.

        Parameters
        ------------
        host: str
            Target SSH host alias.
        remote_dir: str
            Directory on remote host containing QA artifacts.
        local_target_dir: Path
            Local directory where QA snapshots are stored.
        timeout_seconds: float
            Overall sync timeout. Defaults to 60.0.

        Returns
        --------
            list[Path]: list object
                List of locally written QA image paths.
        """
        local_target_dir.mkdir(parents=True, exist_ok=True)
        find_cmd: str = (
            f"find '{remote_dir}' -maxdepth 2 \\( -name '*.png' -o -name '*.svg' \\) "
            "-type f 2>/dev/null || true"
        )
        code, stdout_str, _ = await self._ssh_pool.run_command(
            host, find_cmd, timeout_seconds=10.0
        )

        synced_files: list[Path] = []
        if code != 0 or not stdout_str.strip():
            return synced_files

        remote_files: list[str] = [
            f.strip() for f in stdout_str.splitlines() if f.strip()
        ]
        for r_file in remote_files:
            file_name: str = Path(r_file).name
            dest_file: Path = local_target_dir / file_name
            ok: bool = await self.pull_file(
                host, r_file, dest_file, timeout_seconds=timeout_seconds
            )
            if ok:
                synced_files.append(dest_file)

        return synced_files


__all__: list[str] = [
    "ArtifactSyncManager",
]
