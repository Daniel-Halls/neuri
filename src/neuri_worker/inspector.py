"""Lightweight remote worker machine and job inspector for Neuri.

Queries local machine vitals, scans active neuri_worker jobs, polls Slurm
queues, and enumerates tmux sessions without external dependencies.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from typing import Any


class MachineInspector:
    """Collects machine vitals, batch scheduler status, and job directories.

    Parameters
    ------------
    base_dir: Path | None
        Root directory for neuri_worker data. Defaults to ~/.neuri_worker.

    Returns
    --------
        MachineInspector: MachineInspector instance
            Constructed inspector instance.
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        """Initialize machine inspector with optional worker root directory.

        Parameters
        ------------
        base_dir: Path | None
            Worker directory root. Defaults to ~/.neuri_worker.

        Returns
        --------
            None: NoneType object
                Initializes base directory paths.
        """
        self._base_dir: Path = (
            base_dir if base_dir is not None else Path.home() / ".neuri_worker"
        )
        self._jobs_dir: Path = self._base_dir / "jobs"

    def get_machine_vitals(self) -> dict[str, Any]:
        """Collect local host identification, CPU load, and core counts.

        Parameters
        ------------
        None

        Returns
        --------
            dict[str, Any]: dictionary object
                Dictionary of host vitals including load average and CPU cores.
        """
        host_name: str = socket.gethostname()
        cpu_count: int = os.cpu_count() or 1

        load_list: list[float] = [0.0, 0.0, 0.0]
        if hasattr(os, "getloadavg"):
            try:
                load_tuple: tuple[float, float, float] = os.getloadavg()
                load_list = [
                    round(load_tuple[0], 2),
                    round(load_tuple[1], 2),
                    round(load_tuple[2], 2),
                ]
            except OSError:
                pass

        vitals: dict[str, Any] = {
            "hostname": host_name,
            "cpu_count": cpu_count,
            "load_avg": load_list,
        }
        return vitals

    def get_neuri_jobs(self) -> list[dict[str, Any]]:
        """Scan ~/.neuri_worker/jobs/ for job status payloads.

        Parameters
        ------------
        None

        Returns
        --------
            list[dict[str, Any]]: list object
                List of registered job status dictionaries.
        """
        jobs: list[dict[str, Any]] = []
        if not self._jobs_dir.is_dir():
            return jobs

        for entry in sorted(self._jobs_dir.iterdir()):
            if not entry.is_dir():
                continue
            status_file: Path = entry / "status.json"
            if not status_file.is_file():
                continue

            try:
                content: str = status_file.read_text(encoding="utf-8")
                data: dict[str, Any] = json.loads(content)
                job_record: dict[str, Any] = {
                    "job_id": entry.name,
                    "state": data.get("state", "UNKNOWN"),
                    "start_time": data.get("start_time", ""),
                    "command": data.get("command", ""),
                    "exit_code": data.get("exit_code"),
                }
                jobs.append(job_record)
            except Exception:
                continue

        return jobs

    def get_slurm_jobs(self) -> list[dict[str, Any]]:
        """Query active user jobs from Slurm scheduler via squeue.

        Parameters
        ------------
        None

        Returns
        --------
            list[dict[str, Any]]: list object
                List of active Slurm job records.
        """
        slurm_jobs: list[dict[str, Any]] = []
        squeue_bin: str | None = shutil.which("squeue")
        if squeue_bin is None:
            return slurm_jobs

        cmd: list[str] = [
            squeue_bin,
            "-u",
            os.environ.get("USER", "root"),
            "-h",
            "-o",
            "%i|%j|%T|%M|%P",
        ]
        try:
            res: subprocess.CompletedProcess[str] = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3.0,
                check=False,
            )
            if res.returncode == 0:
                for line in res.stdout.strip().splitlines():
                    parts: list[str] = [p.strip() for p in line.split("|")]
                    if len(parts) >= 5:
                        record: dict[str, Any] = {
                            "slurm_job_id": parts[0],
                            "name": parts[1],
                            "state": parts[2],
                            "elapsed": parts[3],
                            "partition": parts[4],
                        }
                        slurm_jobs.append(record)
        except Exception:
            pass

        return slurm_jobs

    def get_tmux_sessions(self) -> list[str]:
        """Query active detached tmux session names.

        Parameters
        ------------
        None

        Returns
        --------
            list[str]: list object
                List of active tmux session names.
        """
        sessions: list[str] = []
        tmux_bin: str | None = shutil.which("tmux")
        if tmux_bin is None:
            return sessions

        try:
            res: subprocess.CompletedProcess[str] = subprocess.run(
                [tmux_bin, "ls", "-F", "#{session_name}"],
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False,
            )
            if res.returncode == 0:
                for line in res.stdout.strip().splitlines():
                    clean_line: str = line.strip()
                    if clean_line:
                        sessions.append(clean_line)
        except Exception:
            pass

        return sessions

    def inspect_all(self) -> dict[str, Any]:
        """Aggregate machine vitals, local jobs, Slurm jobs, and tmux sessions.

        Parameters
        ------------
        None

        Returns
        --------
            dict[str, Any]: dictionary object
                Comprehensive inspection payload.
        """
        vitals: dict[str, Any] = self.get_machine_vitals()
        neuri_jobs: list[dict[str, Any]] = self.get_neuri_jobs()
        slurm_jobs: list[dict[str, Any]] = self.get_slurm_jobs()
        tmux_sessions: list[str] = self.get_tmux_sessions()

        summary: dict[str, Any] = {
            "hostname": vitals["hostname"],
            "cpu_count": vitals["cpu_count"],
            "load_avg": vitals["load_avg"],
            "neuri_jobs": neuri_jobs,
            "slurm_jobs": slurm_jobs,
            "tmux_sessions": tmux_sessions,
            "inspected_at": datetime.now(timezone.utc).isoformat(),
        }
        return summary


def run_cli_inspection() -> None:
    """CLI entrypoint printing aggregated machine and job status as JSON.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Prints JSON output to standard output.
    """
    inspector: MachineInspector = MachineInspector()
    result: dict[str, Any] = inspector.inspect_all()
    sys.stdout.write(json.dumps(result) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    run_cli_inspection()

__all__: list[str] = [
    "MachineInspector",
    "run_cli_inspection",
]
