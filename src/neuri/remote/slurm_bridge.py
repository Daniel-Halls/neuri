"""Slurm and Detach-and-Reconcile Job Manager for Neuri.

Dispatches asynchronous long-running jobs to Slurm clusters (sbatch) or
detached tmux sessions on remote workstations, reconciling status via status.json.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import shlex
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
        job_id: str | None = None,
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
        job_id: str | None
            Logical job identifier. Defaults to None (inferred from job_dir).

        Returns
        --------
            str: string object
                Complete Slurm submission script content.
        """
        resolved_job_id: str = (
            job_id if job_id is not None else Path(job_dir).name
        )
        escaped_cmd: str = json.dumps(command)
        escaped_jid: str = json.dumps(resolved_job_id)

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
START_TIME="$(date -u +%FT%TZ)"

cat << NEURI_INIT_EOF > "${{STATUS_FILE}}"
{{
  "state": "RUNNING",
  "start_time": "${{START_TIME}}",
  "command": {escaped_cmd},
  "slurm_job_id": "${{SLURM_JOB_ID:-}}",
  "job_id": {escaped_jid}
}}
NEURI_INIT_EOF

cleanup() {{
    EXIT_CODE=$?
    END_TIME="$(date -u +%FT%TZ)"
    if [ ${{EXIT_CODE}} -eq 0 ]; then
        STATE="COMPLETED"
    else
        STATE="FAILED"
    fi
    cat << NEURI_EXIT_EOF > "${{STATUS_FILE}}"
{{
  "state": "${{STATE}}",
  "start_time": "${{START_TIME}}",
  "end_time": "${{END_TIME}}",
  "command": {escaped_cmd},
  "slurm_job_id": "${{SLURM_JOB_ID:-}}",
  "job_id": {escaped_jid},
  "exit_code": ${{EXIT_CODE}}
}}
NEURI_EXIT_EOF
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
        quoted_job_dir: str = shlex.quote(remote_job_dir)
        # Ensure remote job directory exists
        await self._ssh_pool.run_command(host, f"mkdir -p {quoted_job_dir}")

        record_id: str = f"job_{uuid.uuid4().hex[:10]}"
        script_content: str = self.generate_slurm_wrapper(
            command=command,
            job_dir=remote_job_dir,
            partition=partition,
            job_id=record_id,
        )

        script_path: str = f"{remote_job_dir}/submit.sh"
        quoted_script_path: str = shlex.quote(script_path)
        # Write script file on remote host using quoted EOF delimiter
        write_cmd: str = (
            f"cat << 'NEURI_EOF' > {quoted_script_path}\n"
            f"{script_content}\n"
            "NEURI_EOF"
        )
        await self._ssh_pool.run_command(host, write_cmd)

        # Submit via sbatch --parsable
        submit_cmd: str = f"sbatch --parsable {quoted_script_path}"
        code, stdout_str, stderr_str = await self._ssh_pool.run_command(
            host, submit_cmd
        )

        if code != 0:
            raise RuntimeError(
                f"Slurm submission failed on '{host}': {stderr_str}"
            )

        slurm_job_id: str = stdout_str.strip().split(";")[0]
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
            quoted_sched_id: str = shlex.quote(str(remote_sched_id))
            poll_cmd: str = (
                f"sacct -j {quoted_sched_id} "
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

    def generate_slurm_array_wrapper(
        self,
        command_template: str,
        cohort_file: str,
        total_tasks: int,
        job_dir: str,
        max_concurrent: int | None = None,
        partition: str = "standard",
        cpus: int = 4,
        mem_gb: int = 16,
        time_limit: str = "02:00:00",
        job_id: str | None = None,
        array_indices: str | None = None,
    ) -> str:
        """Generate a Bash wrapper script for Slurm subject job array.

        Parameters
        ------------
        command_template: str
            Command containing '${SUBJECT}' placeholder.
        cohort_file: str
            Remote path to subjects.txt listing one subject per line.
        total_tasks: int
            Total number of subjects in the array.
        job_dir: str
            Remote directory where task status JSON files are written.
        max_concurrent: int | None
            Maximum number of simultaneously active array tasks. Defaults to None.
        partition: str
            Slurm partition name. Defaults to 'standard'.
        cpus: int
            CPU cores per task. Defaults to 4.
        mem_gb: int
            Memory in gigabytes per task. Defaults to 16.
        time_limit: str
            Walltime limit. Defaults to '02:00:00'.
        job_id: str | None
            Logical job identifier. Defaults to None.
        array_indices: str | None
            Custom array index string (e.g. '14,37' for retry). Defaults to None.

        Returns
        --------
            str: string object
                Complete Slurm job array submission script.
        """
        resolved_job_id: str = (
            job_id if job_id is not None else Path(job_dir).name
        )
        if array_indices:
            array_spec: str = array_indices
        elif max_concurrent and max_concurrent > 0:
            array_spec = f"1-{total_tasks}%{max_concurrent}"
        else:
            array_spec = f"1-{total_tasks}"

        escaped_cmd: str = json.dumps(command_template)
        escaped_jid: str = json.dumps(resolved_job_id)

        script: str = f"""#!/usr/bin/env bash
#SBATCH --job-name=neuri_array
#SBATCH --output={job_dir}/task_%A_%a.out
#SBATCH --error={job_dir}/task_%A_%a.err
#SBATCH --array={array_spec}
#SBATCH --partition={partition}
#SBATCH --cpus-per-task={cpus}
#SBATCH --mem={mem_gb}G
#SBATCH --time={time_limit}

set -euo pipefail

SUBJECT="$(sed -n "${{SLURM_ARRAY_TASK_ID}}p" "{cohort_file}")"
STATUS_FILE="{job_dir}/task_${{SLURM_ARRAY_TASK_ID}}.json"
START_TIME="$(date -u +%FT%TZ)"

cat << NEURI_ARRAY_INIT_EOF > "${{STATUS_FILE}}"
{{
  "state": "RUNNING",
  "task_id": "${{SLURM_ARRAY_TASK_ID}}",
  "subject": "${{SUBJECT}}",
  "start_time": "${{START_TIME}}",
  "slurm_job_id": "${{SLURM_ARRAY_JOB_ID:-}}",
  "job_id": {escaped_jid}
}}
NEURI_ARRAY_INIT_EOF

cleanup() {{
    EXIT_CODE=$?
    END_TIME="$(date -u +%FT%TZ)"
    if [ ${{EXIT_CODE}} -eq 0 ]; then
        STATE="COMPLETED"
    else
        STATE="FAILED"
    fi
    cat << NEURI_ARRAY_EXIT_EOF > "${{STATUS_FILE}}"
{{
  "state": "${{STATE}}",
  "task_id": "${{SLURM_ARRAY_TASK_ID}}",
  "subject": "${{SUBJECT}}",
  "start_time": "${{START_TIME}}",
  "end_time": "${{END_TIME}}",
  "exit_code": ${{EXIT_CODE}}
}}
NEURI_ARRAY_EXIT_EOF
}}
trap cleanup EXIT

{command_template}
"""
        return script

    async def reconcile_active_job_arrays(
        self,
        host: str,
        slurm_job_id: str,
        total_tasks: int,
    ) -> dict[str, Any]:
        """Query and aggregate task completion progress for a Slurm job array.

        Parameters
        ------------
        host: str
            Target SSH host.
        slurm_job_id: str
            Parent Slurm job array identifier.
        total_tasks: int
            Total number of tasks expected in the array.

        Returns
        --------
            dict[str, Any]: dictionary object
                Cohort progress summary with completed, failed, and running tallies.
        """
        quoted_id: str = shlex.quote(str(slurm_job_id))
        poll_cmd: str = (
            f"sacct -j {quoted_id} "
            "--format=JobID,State,ExitCode -n -P 2>/dev/null || true"
        )
        _, poll_out, _ = await self._ssh_pool.run_command(
            host, poll_cmd, timeout_seconds=10.0
        )

        completed: int = 0
        failed: int = 0
        running: int = 0
        pending: int = 0
        failed_indices: list[int] = []

        for line in poll_out.splitlines():
            parts: list[str] = line.split("|")
            if len(parts) >= 2:
                task_part: str = parts[0].strip()
                state_str: str = parts[1].strip()
                if "_" in task_part and not task_part.endswith((".batch", ".extern")):
                    idx_str = task_part.split("_")[-1]
                    try:
                        task_idx: int = int(idx_str)
                    except ValueError:
                        continue
                    if "COMPLETED" in state_str:
                        completed += 1
                    elif any(
                        f in state_str
                        for f in ("FAILED", "CANCELLED", "TIMEOUT", "NODE_FAIL")
                    ):
                        failed += 1
                        failed_indices.append(task_idx)
                    elif "RUNNING" in state_str:
                        running += 1
                    elif "PENDING" in state_str:
                        pending += 1

        pct: float = (
            round((completed / total_tasks) * 100, 1) if total_tasks > 0 else 0.0
        )
        progress_summary: dict[str, Any] = {
            "slurm_job_id": slurm_job_id,
            "total": total_tasks,
            "completed": completed,
            "running": running,
            "failed": failed,
            "pending": pending,
            "failed_indices": sorted(failed_indices),
            "progress_percent": pct,
        }
        return progress_summary

    def generate_array_retry_command(
        self,
        failed_indices: list[int],
        script_path: str,
    ) -> str:
        """Construct sbatch command resubmitting only failed array task indices.

        Parameters
        ------------
        failed_indices: list[int]
            List of 1-based array task indices that failed.
        script_path: str
            Path to original Slurm submission script on host.

        Returns
        --------
            str: string object
                Targeted sbatch command line string.
        """
        idx_str: str = ",".join(str(i) for i in sorted(failed_indices))
        cmd: str = f"sbatch --array={idx_str} {shlex.quote(script_path)}"
        return cmd


__all__: list[str] = [
    "DetachAndReconcileManager",
]
