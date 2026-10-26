"""Unit tests for remote worker machine inspection and terminal cluster monitor.

Validates MachineInspector vitals and job collection, RemoteHostMonitor SSH
probing, `/machines` slash command routing, and Textual ComputeSidebar widgets.
"""

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from neuri.core.blackboard import Blackboard
from neuri.core.config import NeuriConfig, WorkspaceConfig
from neuri.core.orchestrator import DAGOrchestrator
from neuri.core.slash_commands import SlashCommandResult, SlashCommandRouter
from neuri.remote.monitor import RemoteHostMonitor
from neuri.remote.ssh_pool import SSHControlMasterPool
from neuri.ui.terminal_chat import ComputeSidebar, NeuriChatApp
from neuri_worker.inspector import MachineInspector


def test_machine_inspector_vitals() -> None:
    """Test MachineInspector extracts hostname, CPU count, and load average.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts vitals contain valid hostname, cpu_count, and load list.
    """
    inspector: MachineInspector = MachineInspector()
    vitals: dict[str, Any] = inspector.get_machine_vitals()
    assert "hostname" in vitals
    assert isinstance(vitals["hostname"], str)
    assert vitals["cpu_count"] >= 1
    assert len(vitals["load_avg"]) == 3


def test_machine_inspector_reads_neuri_jobs(tmp_path: Path) -> None:
    """Test MachineInspector scans status.json files in worker jobs directory.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts registered jobs and status attributes are correctly parsed.
    """
    jobs_dir: Path = tmp_path / "jobs"
    job_1: Path = jobs_dir / "job_test_01"
    job_1.mkdir(parents=True)
    status_file: Path = job_1 / "status.json"
    status_file.write_text(
        json.dumps(
            {
                "state": "RUNNING",
                "start_time": "2026-10-26T12:00:00Z",
                "command": "run_bet.sh",
            }
        ),
        encoding="utf-8",
    )

    inspector: MachineInspector = MachineInspector(base_dir=tmp_path)
    jobs: list[dict[str, Any]] = inspector.get_neuri_jobs()
    assert len(jobs) == 1
    assert jobs[0]["job_id"] == "job_test_01"
    assert jobs[0]["state"] == "RUNNING"
    assert jobs[0]["command"] == "run_bet.sh"


def test_machine_inspector_inspect_all_payload(tmp_path: Path) -> None:
    """Test inspect_all aggregates all machine vitals and job lists.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts structure and completeness of aggregated inspection.
    """
    inspector: MachineInspector = MachineInspector(base_dir=tmp_path)
    summary: dict[str, Any] = inspector.inspect_all()
    assert "hostname" in summary
    assert "load_avg" in summary
    assert "neuri_jobs" in summary
    assert "slurm_jobs" in summary
    assert "tmux_sessions" in summary
    assert "inspected_at" in summary


@pytest.mark.asyncio
async def test_remote_host_monitor_local_query() -> None:
    """Test RemoteHostMonitor queries localhost directly without SSH.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts localhost returns online status with vitals.
    """
    monitor: RemoteHostMonitor = RemoteHostMonitor()
    res: dict[str, Any] = await monitor.query_host("localhost")
    assert res["host"] == "localhost"
    assert res["online"] is True
    assert "hostname" in res
    assert isinstance(res["load_avg"], list)


@pytest.mark.asyncio
async def test_remote_host_monitor_remote_ssh_query() -> None:
    """Test RemoteHostMonitor queries remote host via SSHControlMasterPool.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts remote JSON output is parsed into host status.
    """
    mock_pool: AsyncMock = AsyncMock(spec=SSHControlMasterPool)
    payload: dict[str, Any] = {
        "hostname": "remote-hpc",
        "cpu_count": 64,
        "load_avg": [0.45, 0.50, 0.55],
        "neuri_jobs": [{"job_id": "job_99", "state": "RUNNING"}],
        "slurm_jobs": [],
        "tmux_sessions": [],
    }
    mock_pool.run_command.return_value = (0, json.dumps(payload), "")

    monitor: RemoteHostMonitor = RemoteHostMonitor(ssh_pool=mock_pool)
    res: dict[str, Any] = await monitor.query_host("hpc-cluster")
    assert res["host"] == "hpc-cluster"
    assert res["online"] is True
    assert res["hostname"] == "remote-hpc"
    assert res["cpu_count"] == 64
    assert len(res["neuri_jobs"]) == 1
    assert res["neuri_jobs"][0]["job_id"] == "job_99"


@pytest.mark.asyncio
async def test_slash_command_machines_rendering(tmp_path: Path) -> None:
    """Test `/machines` and `/cluster` slash commands format markdown table.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts table structure and online status in rendered markdown.
    """
    bb: Blackboard = Blackboard(tmp_path / "state.db")
    orch: DAGOrchestrator = DAGOrchestrator(blackboard=bb)
    cfg: NeuriConfig = NeuriConfig(
        project=WorkspaceConfig(default_remote_host="localhost")
    )
    router: SlashCommandRouter = SlashCommandRouter(
        workspace_dir=tmp_path,
        config=cfg,
        blackboard=bb,
        orchestrator=orch,
    )

    res_mach: SlashCommandResult = router.execute("/machines")
    assert res_mach.success is True
    assert "Attached Machines" in res_mach.markdown_output
    assert "localhost" in res_mach.markdown_output

    res_cluster: SlashCommandResult = router.execute("/cluster")
    assert res_cluster.success is True
    assert "Attached Machines" in res_cluster.markdown_output


@pytest.mark.asyncio
async def test_textual_compute_sidebar_toggle(tmp_path: Path) -> None:
    """Test ComputeSidebar widget mounts and responds to toggle action.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts sidebar exists and toggles hidden class.
    """
    app: NeuriChatApp = NeuriChatApp(workspace_dir=tmp_path)
    async with app.run_test() as pilot:
        sidebar: ComputeSidebar = app.query_one(
            "#compute-sidebar", ComputeSidebar
        )
        assert sidebar is not None
        assert "hidden" not in sidebar.classes

        # Trigger toggle
        app.action_toggle_sidebar()
        assert "hidden" in sidebar.classes

        # Trigger toggle back
        app.action_toggle_sidebar()
        assert "hidden" not in sidebar.classes
