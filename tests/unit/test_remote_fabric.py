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
    assert "neuri_mux_%C" in pattern
    assert ".ssh" in pattern


def test_ssh_pool_build_ssh_args_includes_low_latency_flags() -> None:
    """Test SSHControlMasterPool injects low-latency performance options.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts GSSAPI, IPQoS, ciphers, and compression flags are present.
    """
    pool: SSHControlMasterPool = SSHControlMasterPool()
    args: list[str] = pool.build_ssh_args("gpu_worker_01")

    assert "ssh" in args
    assert "gpu_worker_01" in args
    assert "GSSAPIAuthentication=no" in args
    assert "IPQoS=lowdelay" in args
    assert "ForwardX11=no" in args
    assert "Compression=no" in args
    assert any("Ciphers=" in a for a in args)


@pytest.mark.asyncio
async def test_ssh_pool_warm_connection_check_and_exec() -> None:
    """Test warm_connection handles active socket and new background master.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts warm_connection logic under mock process execution.
    """
    pool: SSHControlMasterPool = SSHControlMasterPool()

    # Case 1: Check passes (already warm)
    mock_proc_ok: AsyncMock = AsyncMock()
    mock_proc_ok.returncode = 0
    mock_proc_ok.wait.return_value = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc_ok):
        res_ok: bool = await pool.warm_connection("active_node")
        assert res_ok is True

    # Case 2: Check fails then warm command establishes master
    mock_proc_fail: AsyncMock = AsyncMock()
    mock_proc_fail.returncode = 1
    mock_proc_fail.wait.return_value = 1

    with patch(
        "asyncio.create_subprocess_exec",
        side_effect=[mock_proc_fail, mock_proc_ok],
    ):
        res_established: bool = await pool.warm_connection("cold_node")
        assert res_established is True


@pytest.mark.asyncio
async def test_shell_executor_warm_host() -> None:
    """Test ShellCommandExecutor warm_host behavior for local and remote hosts.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts localhost returns True and remote invokes pool.warm_connection.
    """
    from neuri.remote.shell_executor import ShellCommandExecutor

    mock_pool: AsyncMock = AsyncMock(spec=SSHControlMasterPool)
    mock_pool.warm_connection.return_value = True

    executor: ShellCommandExecutor = ShellCommandExecutor(ssh_pool=mock_pool)

    # Localhost should return True immediately without calling pool
    is_local_warm: bool = await executor.warm_host("localhost")
    assert is_local_warm is True
    mock_pool.warm_connection.assert_not_called()

    # Remote host should delegate to ssh_pool.warm_connection
    is_remote_warm: bool = await executor.warm_host("cluster_node")
    assert is_remote_warm is True
    mock_pool.warm_connection.assert_called_once_with("cluster_node")


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


def test_remove_host_record(tmp_path: Path) -> None:
    """Test removing host records from ~/.neuri/hosts.toml.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts host is added and subsequently removed.
    """
    hosts_path: Path = tmp_path / "hosts.toml"
    bootstrapper: RemoteHostBootstrapper = RemoteHostBootstrapper(
        global_hosts_path=hosts_path
    )
    bootstrapper.save_host_record("hpc_node", {"cpus": 64, "memory_gb": 256})

    assert bootstrapper.remove_host_record("nonexistent") is False
    assert bootstrapper.remove_host_record("hpc_node") is True
    assert bootstrapper.remove_host_record("hpc_node") is False


@pytest.mark.asyncio
async def test_persistent_shell_session_local_lifecycle(
    tmp_path: Path,
) -> None:
    """Test PersistentShellSession starts, runs commands, and closes cleanly.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts ultra-low latency execution and exit code preservation.
    """
    from neuri.remote.shell_executor import (
        PersistentShellSession,
        ShellCommandExecutor,
    )

    pool: SSHControlMasterPool = SSHControlMasterPool()
    session: PersistentShellSession = PersistentShellSession(
        host="localhost",
        is_local=True,
        workspace_dir=tmp_path,
        ssh_pool=pool,
    )

    assert session.is_alive() is False
    started: bool = await session.start()
    assert started is True
    assert session.is_alive() is True

    # Command 1: success
    code1, out1, dur1 = await session.execute("echo 'fast_session_test'")
    assert code1 == 0
    assert "fast_session_test" in out1
    assert dur1 < 0.2

    # Command 2: error status
    code2, out2, dur2 = await session.execute("ls nonexistent_target_path_xyz")
    assert code2 != 0
    assert "nonexistent_target_path_xyz" in out2

    await session.close()
    assert session.is_alive() is False

    # Test ShellCommandExecutor close_all cleans up registered sessions
    executor: ShellCommandExecutor = ShellCommandExecutor(
        workspace_dir=tmp_path, ssh_pool=pool
    )
    res = await executor.execute("echo 'executor_persistent'")
    assert res.exit_code == 0
    assert "executor_persistent" in res.stdout
    await executor.close_all()
