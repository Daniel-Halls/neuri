"""Unit tests for SlashCommandRouter, DAGOrchestrator, and NeuriSessionEngine.

Tests slash command execution (/init, /skills, /status, /harness, /retry,
/cancel, /clear, /help, /exit), DAG planning, event bus subscriptions,
and turn accumulation (Milestone 5).
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from neuri.core.blackboard import Blackboard
from neuri.core.config import NeuriConfig, load_config
from neuri.core.orchestrator import DAGOrchestrator
from neuri.core.schemas import (
    ChatRole,
    ChatTurn,
    NeuriTaskEnvelope,
    RemoteArtifact,
    SanitizedNeuroHeader,
    SessionEvent,
    SessionEventType,
    TaskNode,
    TaskState,
)
from neuri.core.session import NeuriSessionEngine
from neuri.core.slash_commands import SlashCommandResult, SlashCommandRouter
from neuri.remote.bootstrap import RemoteHostBootstrapper


@pytest.fixture
def test_workspace(tmp_path: Path) -> Path:
    """Provide a clean temporary workspace directory.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        Path: Path object
            Temporary workspace directory path.
    """
    ws: Path = tmp_path / "test_workspace"
    ws.mkdir()
    return ws


@pytest.fixture
def test_blackboard(test_workspace: Path) -> Blackboard:
    """Provide an initialized Blackboard instance in test workspace.

    Parameters
    ------------
    test_workspace: Path
        Workspace fixture.

    Returns
    --------
        Blackboard: Blackboard instance
            Initialized SQLite WAL Blackboard object.
    """
    db_file: Path = test_workspace / "state.db"
    bb: Blackboard = Blackboard(db_file)
    return bb


@pytest.fixture
def slash_router(
    test_workspace: Path, test_blackboard: Blackboard
) -> SlashCommandRouter:
    """Provide an initialized SlashCommandRouter.

    Parameters
    ------------
    test_workspace: Path
        Workspace fixture.
    test_blackboard: Blackboard
        Blackboard fixture.

    Returns
    --------
        SlashCommandRouter: SlashCommandRouter instance
            Constructed router instance.
    """
    cfg: NeuriConfig = load_config(test_workspace)
    orch: DAGOrchestrator = DAGOrchestrator(blackboard=test_blackboard)
    router: SlashCommandRouter = SlashCommandRouter(
        workspace_dir=test_workspace,
        config=cfg,
        blackboard=test_blackboard,
        orchestrator=orch,
    )
    return router


# ---------------------------------------------------------------------------
# Test Suite 1: SlashCommandRouter
# ---------------------------------------------------------------------------


def test_slash_router_detects_slash_commands(
    slash_router: SlashCommandRouter,
) -> None:
    """Test slash command syntax detection on various inputs.

    Parameters
    ------------
    slash_router: SlashCommandRouter
        Active router fixture.

    Returns
    --------
        None: NoneType object
            Asserts detection returns expected booleans.
    """
    assert slash_router.is_slash_command("/init") is True
    assert slash_router.is_slash_command("/skills list") is True
    assert slash_router.is_slash_command("  /status  ") is True
    assert slash_router.is_slash_command("perform brain extraction") is False
    assert slash_router.is_slash_command("/") is False


def test_slash_command_init(
    slash_router: SlashCommandRouter, test_workspace: Path
) -> None:
    """Test /init command initializes .neuri directory and assets.

    Parameters
    ------------
    slash_router: SlashCommandRouter
        Active router fixture.
    test_workspace: Path
        Workspace fixture.

    Returns
    --------
        None: NoneType object
            Asserts .neuri workspace is created with config and db files.
    """
    res: SlashCommandResult = slash_router.execute("/init")
    assert res.success is True
    assert res.command == "/init"
    assert res.action == "reload_config"
    assert "Workspace Initialized" in res.markdown_output

    dot_dir: Path = test_workspace / ".neuri"
    assert dot_dir.is_dir()
    assert (dot_dir / "neuri.toml").is_file()
    assert (dot_dir / "state.db").is_file()
    assert (dot_dir / "references.bib").is_file()


def test_slash_command_skills_catalog(
    slash_router: SlashCommandRouter,
) -> None:
    """Test /skills renders catalog markdown table.

    Parameters
    ------------
    slash_router: SlashCommandRouter
        Active router fixture.

    Returns
    --------
        None: NoneType object
            Asserts skills table is generated.
    """
    res: SlashCommandResult = slash_router.execute("/skills")
    assert res.success is True
    assert "Neuroscience Skills Catalog" in res.markdown_output
    assert "bids-standard" in res.markdown_output


def test_slash_command_skills_inspect(
    slash_router: SlashCommandRouter,
) -> None:
    """Test /skills <skill_id> inspects specific skill details.

    Parameters
    ------------
    slash_router: SlashCommandRouter
        Active router fixture.

    Returns
    --------
        None: NoneType object
            Asserts skill detail card is generated.
    """
    res: SlashCommandResult = slash_router.execute("/skills bids-standard")
    assert res.success is True
    assert "Skill: BIDS & Neuro File IO" in res.markdown_output
    assert "bids-standard" in res.markdown_output


def test_slash_command_status(
    slash_router: SlashCommandRouter,
) -> None:
    """Test /status renders workspace and configuration status.

    Parameters
    ------------
    slash_router: SlashCommandRouter
        Active router fixture.

    Returns
    --------
        None: NoneType object
            Asserts system status card is returned.
    """
    res: SlashCommandResult = slash_router.execute("/status")
    assert res.success is True
    assert "Neuri System Status" in res.markdown_output


def test_slash_command_harness(
    slash_router: SlashCommandRouter,
) -> None:
    """Test /harness displays routing and supports dynamic role updates.

    Parameters
    ------------
    slash_router: SlashCommandRouter
        Active router fixture.

    Returns
    --------
        None: NoneType object
            Asserts table display and dynamic update.
    """
    view_res: SlashCommandResult = slash_router.execute("/harness")
    assert view_res.success is True
    assert "Harness Routing Map" in view_res.markdown_output

    update_res: SlashCommandResult = slash_router.execute(
        "/harness neuroimaging_specialist codex"
    )
    assert update_res.success is True
    assert "Updated harness routing" in update_res.markdown_output


def test_slash_command_remote_remove(
    slash_router: SlashCommandRouter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test /remote list and /remote remove slash commands.

    Parameters
    ------------
    slash_router: SlashCommandRouter
        Active router fixture.
    tmp_path: Path
        Pytest temporary directory fixture.
    monkeypatch: pytest.MonkeyPatch
        Pytest monkeypatch fixture.

    Returns
    --------
        None: NoneType object
            Asserts host listing and removal via slash commands.
    """
    fake_home: Path = tmp_path / "fake_home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

    hosts_file: Path = fake_home / ".neuri" / "hosts.toml"
    hosts_file.parent.mkdir(parents=True, exist_ok=True)
    bootstrapper: RemoteHostBootstrapper = RemoteHostBootstrapper(
        global_hosts_path=hosts_file
    )
    bootstrapper.save_host_record("hpc_worker", {"cpus": 32})

    list_res: SlashCommandResult = slash_router.execute("/remote list")
    assert list_res.success is True

    # Test removing non-existent host
    fail_res: SlashCommandResult = slash_router.execute(
        "/remote remove invalid_host"
    )
    assert fail_res.success is False
    assert "not found" in fail_res.markdown_output

    # Test removing existing host
    ok_res: SlashCommandResult = slash_router.execute(
        "/remote remove hpc_worker"
    )
    assert ok_res.success is True
    assert "Host Removed: `hpc_worker`" in ok_res.markdown_output


def test_slash_command_clear(
    slash_router: SlashCommandRouter,
) -> None:
    """Test /clear returns clear_chat action.

    Parameters
    ------------
    slash_router: SlashCommandRouter
        Active router fixture.

    Returns
    --------
        None: NoneType object
            Asserts action='clear_chat'.
    """
    res: SlashCommandResult = slash_router.execute("/clear")
    assert res.success is True
    assert res.action == "clear_chat"


def test_slash_command_help(
    slash_router: SlashCommandRouter,
) -> None:
    """Test /help returns markdown command table.

    Parameters
    ------------
    slash_router: SlashCommandRouter
        Active router fixture.

    Returns
    --------
        None: NoneType object
            Asserts markdown reference card is returned.
    """
    res: SlashCommandResult = slash_router.execute("/help")
    assert res.success is True
    assert "/init" in res.markdown_output
    assert "/skills" in res.markdown_output


def test_slash_command_exit(
    slash_router: SlashCommandRouter,
) -> None:
    """Test /exit returns exit_app action.

    Parameters
    ------------
    slash_router: SlashCommandRouter
        Active router fixture.

    Returns
    --------
        None: NoneType object
            Asserts action='exit_app'.
    """
    res: SlashCommandResult = slash_router.execute("/exit")
    assert res.success is True
    assert res.action == "exit_app"


def test_slash_command_unknown(
    slash_router: SlashCommandRouter,
) -> None:
    """Test unknown command returns error message.

    Parameters
    ------------
    slash_router: SlashCommandRouter
        Active router fixture.

    Returns
    --------
        None: NoneType object
            Asserts failure and unknown command notice.
    """
    res: SlashCommandResult = slash_router.execute("/unknown_magic")
    assert res.success is False
    assert "Unknown command: `/unknown_magic`" in res.markdown_output


# ---------------------------------------------------------------------------
# Test Suite 2: DAGOrchestrator Planning & Node Control
# ---------------------------------------------------------------------------


def test_orchestrator_plan_workflow(
    test_blackboard: Blackboard,
) -> None:
    """Test planning a workflow from natural language creates DAG nodes.

    Parameters
    ------------
    test_blackboard: Blackboard
        Active Blackboard fixture.

    Returns
    --------
        None: NoneType object
            Asserts workflow and ready nodes are registered.
    """
    orch: DAGOrchestrator = DAGOrchestrator(blackboard=test_blackboard)
    wf_id: str = orch.plan_workflow_from_prompt(
        "Validate BIDS dataset and perform BET brain extraction"
    )
    assert wf_id.startswith("wf_")

    ready: list[TaskNode] = test_blackboard.get_ready_nodes(wf_id)
    assert len(ready) >= 1
    assert ready[0].state == TaskState.PENDING


def test_orchestrator_retry_and_cancel_node(
    test_blackboard: Blackboard,
) -> None:
    """Test manual retry and cancellation of nodes in WAITING_OPERATOR.

    Parameters
    ------------
    test_blackboard: Blackboard
        Active Blackboard fixture.

    Returns
    --------
        None: NoneType object
            Asserts state transitions to PENDING and CANCELLED.
    """
    orch: DAGOrchestrator = DAGOrchestrator(blackboard=test_blackboard)
    wf_id: str = orch.plan_workflow_from_prompt("Inspect NIfTI header")
    ready: list[TaskNode] = test_blackboard.get_ready_nodes(wf_id)
    node_id: str = ready[0].node_id

    # Simulate node paused in WAITING_OPERATOR
    test_blackboard.update_node_state(node_id, TaskState.WAITING_OPERATOR)

    # Test retry
    retried: bool = orch.retry_node(node_id)
    assert retried is True
    node: TaskNode | None = test_blackboard.get_node(node_id)
    assert node is not None
    assert node.state == TaskState.PENDING

    # Test cancel
    cancelled: bool = orch.cancel_node(node_id)
    assert cancelled is True
    node = test_blackboard.get_node(node_id)
    assert node is not None
    assert node.state == TaskState.CANCELLED


# ---------------------------------------------------------------------------
# Test Suite 3: NeuriSessionEngine
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_engine_slash_command_turn(
    test_workspace: Path,
    test_blackboard: Blackboard,
) -> None:
    """Test submitting a slash command produces user and assistant turns.

    Parameters
    ------------
    test_workspace: Path
        Workspace fixture.
    test_blackboard: Blackboard
        Blackboard fixture.

    Returns
    --------
        None: NoneType object
            Asserts user and assistant turns are recorded in history.
    """
    engine: NeuriSessionEngine = NeuriSessionEngine(
        workspace_dir=test_workspace,
        blackboard=test_blackboard,
    )
    turn: ChatTurn = await engine.submit_user_input("/status")

    assert turn.role == ChatRole.ASSISTANT
    assert "Neuri System Status" in turn.content

    history: list[ChatTurn] = engine.turns
    assert len(history) == 2
    assert history[0].role == ChatRole.USER
    assert history[0].content == "/status"
    assert history[1].role == ChatRole.ASSISTANT


@pytest.mark.asyncio
async def test_session_engine_event_bus(
    test_workspace: Path,
    test_blackboard: Blackboard,
) -> None:
    """Test subscribing to SessionEngine event stream dispatches events.

    Parameters
    ------------
    test_workspace: Path
        Workspace fixture.
    test_blackboard: Blackboard
        Blackboard fixture.

    Returns
    --------
        None: NoneType object
            Asserts subscriber callback receives events.
    """
    engine: NeuriSessionEngine = NeuriSessionEngine(
        workspace_dir=test_workspace,
        blackboard=test_blackboard,
    )
    received_events: list[SessionEvent] = []

    def on_event(ev: SessionEvent) -> None:
        """Collect session events.

        Parameters
        ------------
        ev: SessionEvent
            Incoming session event.

        Returns
        --------
            None: NoneType object
                Appends to collection list.
        """
        received_events.append(ev)

    engine.subscribe(on_event)
    await engine.submit_user_input("/help")

    assert len(received_events) >= 2
    event_types: list[SessionEventType] = [e.event_type for e in received_events]
    assert SessionEventType.USER_MESSAGE in event_types
    assert SessionEventType.STATUS_UPDATE in event_types

    # Test unsubscribe
    engine.unsubscribe(on_event)
    count_before: int = len(received_events)
    await engine.submit_user_input("/clear")
    assert len(received_events) == count_before
