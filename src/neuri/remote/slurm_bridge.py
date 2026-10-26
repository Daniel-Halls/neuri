"""Slurm and Detach-and-Reconcile Job Manager for Neuri.

Dispatches asynchronous long-running jobs to Slurm clusters (sbatch) or
detached tmux sessions on remote workstations, reconciling status via status.json.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
import uuid

from neuri.core.blackboard import Blackboard
from neuri.core.schemas import TaskState
from neuri.remote.ssh_pool import SSHControlMasterPool


class DetachAndReconcileManager:
    """Manages submission and asynchronous reconciliation of remote jobs.

    Parameters
    ------------
    ssh_pool: SSHControlMasterPool | None
        SSH connection pool instance. Defaults to None (auto-initialized).

    Returns
    --------
        DetachAndReconcileManager: DetachAndReconcileManager instance
            Constructed job manager.
    """

    def __init__(self, ssh_pool: SSHControlMasterPool | None = None) -> None:
        """Initialize job manager with SSH connection pool.

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

    def generate_slurm_wrapper(
        self,
        command: str,
        job_dir: str,
        partition: str = "standard",
        cpus: int = 4,
        mem_gb: int = 16,
        time_limit: str = "02:00:00",
    ) -> str:
        """Generate a Bash wrapper script for Slurm sbatch with status trap.

        Parameters
        ------------
        command: str
            Raw command line to execute.
        job_dir: str
            Remote directory where status.json and logs will be written.
        partition: str
            Slurm partition name. Defaults to 'standard'.
        cpus: int
            CPU cores count. Defaults to 4.
        mem_gb: int
            Memory in gigabytes. Defaults to 16.
        time_limit: str
            Walltime limit string. Defaults to '02:00:00'.

        Returns
        --------
            str: string object
                Complete Slurm submission script content.
        """
        script: str = f"""#!/usr/bin/env bash
#SBATCH --job-name=neuri_job
#SBATCH --output={job_dir}/slurm_%j.out
#SBATCH --error={job_dir}/slurm_%j.err
#SBATCH --partition={partition}
#SBATCH --cpus-per-task={cpus}
#SBATCH --mem={mem_gb}G
#SBATCH --time={time_limit}

set -euo pipefail
STATUS_FILE="{job_dir}/status.json"

echo '{{"state": "RUNNING", "start_time": "'$(date -u +%FT%TZ)'"}}' > "${{STATUS_FILE}}"

cleanup() {{
    EXIT_CODE=$?
    if [ ${{EXIT_CODE}} -eq 0 ]; then
        STATE="COMPLETED"
    else
        STATE="FAILED"
    fi
    echo '{{"state": "'"${{STATE}}"'"' > "${{STATUS_FILE}}"
    echo ', "exit_code": '"${{EXIT_CODE}}"'}}' >> "${{STATUS_FILE}}"
}}
trap cleanup EXIT

{command}
"""
        return script

    async def submit_slurm_job(
        self,
        host: str,
        command: str,
        remote_job_dir: str,
        blackboard: Blackboard,
        node_id: str,
        partition: str = "standard",
    ) -> str:
        """Submit a command as a Slurm sbatch job and record in Blackboard.

        Parameters
        ------------
        host: str
            Target SSH host alias.
        command: str
            Scientific pipeline command to execute.
        remote_job_dir: str
            Remote directory path for job execution.
        blackboard: Blackboard
            Blackboard instance for state recording.
        node_id: str
            Associated task node identifier.
        partition: str
            Slurm partition. Defaults to 'standard'.

        Returns
        --------
            str: string object
                Assigned Slurm job identifier string.
        """
        # Ensure remote job directory exists
        await self._ssh_pool.run_command(host, f"mkdir -p {remote_job_dir}")

        script_content: str = self.generate_slurm_wrapper(
            command=command,
            job_dir=remote_job_dir,
            partition=partition,
        )

        script_path: str = f"{remote_job_dir}/submit.sh"
        # Write script file on remote host
        write_cmd: str = f"cat << 'EOF' > {script_path}\n{script_content}\nEOF"
        await self._ssh_pool.run_command(host, write_cmd)

        # Submit via sbatch --parsable
        submit_cmd: str = f"sbatch --parsable {script_path}"
        code, stdout_str, stderr_str = await self._ssh_pool.run_command(
            host, submit_cmd
        )

        if code != 0:
            raise RuntimeError(
                f"Slurm submission failed on '{host}': {stderr_str}"
            )

        slurm_job_id: str = stdout_str.strip().split(";")[0]
        record_id: str = f"job_{uuid.uuid4().hex[:10]}"
        status_uri: str = f"{host}://{remote_job_dir}/status.json"

        # Record in SQLite remote_jobs table
        blackboard.register_remote_job(
            job_id=record_id,
            node_id=node_id,
            host=host,
            scheduler_type="slurm",
            scheduler_job_id=slurm_job_id,
            status_uri=status_uri,
        )
        return slurm_job_id

    async def reconcile_active_jobs(
        self, blackboard: Blackboard
    ) -> list[dict[str, Any]]:
        """Query active remote jobs, poll status, and reconcile Blackboard state.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard instance storing remote jobs and task nodes.

        Returns
        --------
            list[dict[str, Any]]: list object
                List of reconciled job summary dictionaries.
        """
        active_jobs: list[dict[str, Any]] = blackboard.get_active_remote_jobs()
        reconciled_list: list[dict[str, Any]] = []

        for job in active_jobs:
            job_id: str = job["job_id"]
            node_id: str = job["node_id"]
            host: str = job["host"]
            remote_sched_id: str = job["scheduler_job_id"]
            status_uri: str = job["status_uri"]

            # Poll sacct
            poll_cmd: str = (
                f"sacct -j {remote_sched_id} "
                "--format=JobID,State,ExitCode -n -P 2>/dev/null || true"
            )
            _, poll_out, _ = await self._ssh_pool.run_command(
                host, poll_cmd, timeout_seconds=10.0
            )

            status_str: str = "RUNNING"
            for line in poll_out.splitlines():
                parts = line.split("|")
                if len(parts) >= 2 and parts[0] == remote_sched_id:
                    status_str = parts[1].strip()
                    break

            if "COMPLETED" in status_str:
                blackboard.update_remote_job_state(job_id, "COMPLETED")
                blackboard.update_node_state(
                    node_id,
                    TaskState.COMPLETED,
                    summary_result=f"Slurm job {remote_sched_id} completed",
                )
            elif any(
                f in status_str
                for f in ("FAILED", "CANCELLED", "TIMEOUT", "NODE_FAIL")
            ):
                blackboard.update_remote_job_state(job_id, "FAILED")
                blackboard.update_node_state(
                    node_id,
                    TaskState.WAITING_OPERATOR,
                    diagnostic_feedback=f"Slurm job failed with state: {status_str}",
                    summary_result=f"Slurm failure: {status_str}",
                )

            reconciled_list.append(
                {"job_id": job_id, "remote_id": remote_sched_id, "status": status_str}
            )

        return reconciled_list


__all__: list[str] = [
    "DetachAndReconcileManager",
]
