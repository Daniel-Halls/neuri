"""Unit tests for Neuri Hub-and-Spoke Remote Execution Fabric.

Tests SSH ControlMaster multiplexing, remote capability detection and bootstrapping,
Slurm detach-and-reconcile state transitions, and selective artifact synchronization.
"""

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from neuri.core.blackboard import Blackboard
from neuri.core.schemas import TaskNode, TaskState
from neuri.remote.bootstrap import RemoteHostBootstrapper
from neuri.remote.rsync_artifacts import ArtifactSyncManager
from neuri.remote.slurm_bridge import DetachAndReconcileManager
from neuri.remote.ssh_pool import SSHControlMasterPool


@pytest.fixture
def test_bb(tmp_path: Path) -> Blackboard:
    """Provide a temporary Blackboard instance for remote jobs testing.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        Blackboard: Blackboard instance
            Initialized SQLite WAL store.
    """
    db_file: Path = tmp_path / "test_state.db"
    return Blackboard(db_file)


def test_ssh_pool_socket_path_generation() -> None:
    """Test SSH ControlMaster socket path formatting.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts socket path format.
    """
    pool: SSHControlMasterPool = SSHControlMasterPool()
    pattern: str = pool.get_control_path_pattern()
    assert "neuri_mux_%h_%p_%r" in pattern
    assert ".ssh" in pattern


def test_slurm_wrapper_script_generation() -> None:
    """Test Slurm wrapper script contains traps and status.json updates.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts bash script content.
    """
    manager: DetachAndReconcileManager = DetachAndReconcileManager()
    script: str = manager.generate_slurm_wrapper(
        command="fslmaths in.nii -add 1 out.nii",
        job_dir="/scratch/job_123",
        partition="standard",
        cpus=8,
        mem_gb=32,
        time_limit="04:00:00",
    )
    assert "#SBATCH --partition=standard" in script
    assert "#SBATCH --cpus-per-task=8" in script
    assert "#SBATCH --mem=32G" in script
    assert 'STATUS_FILE="/scratch/job_123/status.json"' in script
    assert 'STATE="COMPLETED"' in script
    assert "trap cleanup EXIT" in script
    assert "fslmaths in.nii -add 1 out.nii" in script


@pytest.mark.asyncio
async def test_reconcile_active_jobs_transitions_states(test_bb: Blackboard) -> None:
    """Test sacct output reconciles remote job and node state in Blackboard.

    Parameters
    ------------
    test_bb: Blackboard
        Blackboard fixture.

    Returns
    --------
        None: NoneType object
            Asserts node completed upon Slurm COMPLETED state.
    """
    test_bb.create_workflow("wf_rem_01", "Remote job test")
    node: TaskNode = TaskNode(
        node_id="node_rem_01",
        workflow_id="wf_rem_01",
        agent_role="compute_operator",
        harness_id="slurm",
        state=TaskState.RUNNING,
    )
    test_bb.create_node(node)

    test_bb.register_remote_job(
        job_id="job_001",
        node_id="node_rem_01",
        host="ada",
        scheduler_type="slurm",
        scheduler_job_id="999888",
        status_uri="ada:///scratch/job_001/status.json",
    )

    mock_pool: AsyncMock = AsyncMock(spec=SSHControlMasterPool)
    mock_pool.run_command.return_value = (
        0,
        "999888|COMPLETED|0:0\n",
        "",
    )

    manager: DetachAndReconcileManager = DetachAndReconcileManager(ssh_pool=mock_pool)
    reconciled = await manager.reconcile_active_jobs(test_bb)

    assert len(reconciled) == 1
    assert reconciled[0]["status"] == "COMPLETED"

    updated_node = test_bb.get_node("node_rem_01")
    assert updated_node is not None
    assert updated_node.state == TaskState.COMPLETED


def test_artifact_sync_manager_limits() -> None:
    """Test that ArtifactSyncManager enforces file size ceilings.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts size ceiling is defined and bounded.
    """
    syncer: ArtifactSyncManager = ArtifactSyncManager()
    assert syncer.MAX_FILE_SIZE_BYTES == 10 * 1024 * 1024
