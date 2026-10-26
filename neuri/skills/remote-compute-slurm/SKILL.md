---
name: remote-compute-slurm
description: Remote HPC execution, Slurm sbatch script generation, GPU partition scheduling, and sacct job tracking.
triggers:
  - sbatch generation
  - GPU scheduling
  - job status
  - remote cluster
modalities:
  - table
  - report_qa
---

# Remote HPC & Slurm Execution Skill

## 1. Core Responsibilities
- Generate robust, reproducible Slurm submission scripts (`sbatch`) for CPU and GPU partitions.
- Manage container bindings for Apptainer / Singularity `.sif` images with necessary scratch mounts (`/scratch`, `/local`, `/tmp`).
- Implement the Detach-and-Reconcile pattern for asynchronous remote jobs lasting longer than 20 seconds.
- Monitor remote job status via `squeue` and `sacct` and parse exit codes from `<job_dir>/status.json`.

## 2. Standard Slurm Script Template
```bash
#!/usr/bin/env bash
#SBATCH --job-name=neuri_{NODE_ID}
#SBATCH --output={JOB_DIR}/slurm_%j.out
#SBATCH --error={JOB_DIR}/slurm_%j.err
#SBATCH --partition={PARTITION}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task={CPUS}
#SBATCH --mem={MEM_GB}G
#SBATCH --time={WALLTIME}
{GPU_DIRECTIVE}

set -euo pipefail

# Sentinel status recorder
STATUS_FILE="{JOB_DIR}/status.json"
echo '{"state": "RUNNING", "job_id": "'"$SLURM_JOB_ID"'", "start_time": "'$(date -u +%FT%TZ)'"}' > "${STATUS_FILE}"

cleanup() {
    EXIT_CODE=$?
    if [ ${EXIT_CODE} -eq 0 ]; then
        STATE="COMPLETED"
    else
        STATE="FAILED"
    fi
    echo '{"state": "'"${STATE}"'", "exit_code": '"${EXIT_CODE}"', "end_time": "'$(date -u +%FT%TZ)'"}' > "${STATUS_FILE}"
}
trap cleanup EXIT

# Execute containerized pipeline
apptainer exec --nv \
    --bind {BIDS_DIR}:/data:ro \
    --bind {OUTPUT_DIR}:/out \
    --bind {SCRATCH_DIR}:/tmp \
    {CONTAINER_SIF} \
    {COMMAND}
```

## 3. HPC Safety & Pre-Flight Rules
- **Disk Quota Check:** Verify available scratch capacity before submitting batch processing.
- **Parsable Submission:** Always invoke `sbatch --parsable` so the orchestrator captures the numerical job ID directly.
- **Fail-Safe Polling:** Poll `sacct -j <job_id> --format=JobID,State,ExitCode -n -P` at bounded exponential backoff intervals (never faster than 5 seconds to avoid overloading cluster schedulers).
