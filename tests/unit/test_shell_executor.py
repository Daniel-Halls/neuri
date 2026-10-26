"""Unit tests for Neuri local and remote shell command executor subsystem.

Tests execution on localhost, remote SSH command forwarding, timeout handling,
Markdown output formatting, session engine integration, and /shell commands.
"""

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from neuri.core.blackboard import Blackboard
from neuri.core.config import NeuriConfig
from neuri.core.orchestrator import DAGOrchestrator
from neuri.core.schemas import ChatRole, ChatTurn
from neuri.core.session import NeuriSessionEngine
from neuri.core.slash_commands import SlashCommandResult, SlashCommandRouter
from neuri.remote.bootstrap import RemoteHostBootstrapper
from neuri.remote.shell_executor import (
    ShellCommandExecutor,
    ShellExecutionResult,
)
from neuri.remote.ssh_pool import SSHControlMasterPool


@pytest.mark.asyncio
async def test_shell_executor_local_echo(tmp_path: Path) -> None:
    """Test local command execution returns stdout and exit code 0.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts clean return code and expected stdout text.
    """
    executor: ShellCommandExecutor = ShellCommandExecutor(workspace_dir=tmp_path)
    res: ShellExecutionResult = await executor.execute(
        command="echo 'neuri shell mode'", host="localhost"
    )

    assert res.exit_code == 0
    assert "neuri shell mode" in res.stdout
    assert res.host == "localhost"
    assert res.duration_seconds >= 0.0


@pytest.mark.asyncio
async def test_shell_executor_local_nonzero_exit(tmp_path: Path) -> None:
    """Test local command execution capturing non-zero exit codes.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts non-zero return code and stderr message.
    """
    executor: ShellCommandExecutor = ShellCommandExecutor(workspace_dir=tmp_path)
    res: ShellExecutionResult = await executor.execute(
        command="exit 42", host="127.0.0.1"
    )

    assert res.exit_code == 42
    assert res.host == "127.0.0.1"


@pytest.mark.asyncio
async def test_shell_executor_local_timeout(tmp_path: Path) -> None:
    """Test local command timeout handling.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts timeout return code and explanatory stderr message.
    """
    executor: ShellCommandExecutor = ShellCommandExecutor(workspace_dir=tmp_path)
    res: ShellExecutionResult = await executor.execute(
        command="sleep 5", host="localhost", timeout_seconds=0.1
    )

    assert res.exit_code == -2
    assert "timed out" in res.stderr


@pytest.mark.asyncio
async def test_shell_executor_remote_forwarding(tmp_path: Path) -> None:
    """Test remote execution delegates to SSHControlMasterPool.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts mock pool is called with target host and command.
    """
    mock_pool: AsyncMock = AsyncMock(spec=SSHControlMasterPool)
    mock_pool.run_command.return_value = (0, "gpu_node_ready\n", "")

    executor: ShellCommandExecutor = ShellCommandExecutor(
        workspace_dir=tmp_path, ssh_pool=mock_pool
    )
    res: ShellExecutionResult = await executor.execute(
        command="nvidia-smi -L", host="gpu_cluster"
    )

    assert res.exit_code == 0
    assert "gpu_node_ready" in res.stdout
    assert res.host == "gpu_cluster"
    mock_pool.run_command.assert_awaited_once_with(
        host="gpu_cluster",
        command="nvidia-smi -L",
        timeout_seconds=120.0,
    )


def test_shell_executor_format_markdown_card() -> None:
    """Test Markdown formatting for successful and failed executions.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts Markdown tags, code fences, and status badges.
    """
    executor: ShellCommandExecutor = ShellCommandExecutor()
    res_ok: ShellExecutionResult = ShellExecutionResult(
        command="git status",
        host="localhost",
        exit_code=0,
        stdout="On branch main\nnothing to commit",
        stderr="",
        duration_seconds=0.04,
    )
    card_ok: str = executor.format_markdown_card(res_ok)
    assert "### Shell Output: `localhost`" in card_ok
    assert "✓ Success" in card_ok
    assert "```bash" in card_ok
    assert "On branch main" in card_ok

    res_fail: ShellExecutionResult = ShellExecutionResult(
        command="cat missing.txt",
        host="ada",
        exit_code=1,
        stdout="",
        stderr="cat: missing.txt: No such file or directory",
        duration_seconds=0.12,
    )
    card_fail: str = executor.format_markdown_card(res_fail)
    assert "### Shell Output: `ada`" in card_fail
    assert "✗ Exit Code: 1" in card_fail
    assert "Standard Error:" in card_fail
    assert "No such file or directory" in card_fail


def test_shell_executor_get_available_hosts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test discovering available machines from ~/.neuri/hosts.toml.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.
    monkeypatch: pytest.MonkeyPatch
        Pytest monkeypatch fixture.

    Returns
    --------
        None: NoneType object
            Asserts localhost and configured remote hosts are present.
    """
    fake_home: Path = tmp_path / "fake_home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

    hosts_file: Path = fake_home / ".neuri" / "hosts.toml"
    hosts_file.parent.mkdir(parents=True, exist_ok=True)
    bootstrapper: RemoteHostBootstrapper = RemoteHostBootstrapper(
        global_hosts_path=hosts_file
    )
    bootstrapper.save_host_record("hpc_node_1", {"cpus": 64})
    bootstrapper.save_host_record("gpu_box", {"cpus": 16})

    executor: ShellCommandExecutor = ShellCommandExecutor(workspace_dir=tmp_path)
    hosts: list[str] = executor.get_available_hosts()

    assert "localhost" in hosts
    assert "hpc_node_1" in hosts
    assert "gpu_box" in hosts
    assert hosts[0] == "localhost"


@pytest.mark.asyncio
async def test_session_engine_execute_shell_command(tmp_path: Path) -> None:
    """Test NeuriSessionEngine.execute_shell_command records turns.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts turn creation and shell output in session turns.
    """
    engine: NeuriSessionEngine = NeuriSessionEngine(workspace_dir=tmp_path)
    turn: ChatTurn = await engine.execute_shell_command(
        command="echo 'session test'", host="localhost"
    )

    assert turn.role == ChatRole.ASSISTANT
    assert "### Shell Output: `localhost`" in turn.content
    assert "session test" in turn.content
    assert len(engine.turns) == 2  # user shell turn + assistant turn


def test_slash_command_shell(tmp_path: Path) -> None:
    """Test /shell and /sh slash commands through SlashCommandRouter.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts execution outcome and markdown output.
    """
    bb: Blackboard = Blackboard(tmp_path / "state.db")
    orch: DAGOrchestrator = DAGOrchestrator(blackboard=bb)
    config: NeuriConfig = NeuriConfig()
    router: SlashCommandRouter = SlashCommandRouter(
        workspace_dir=tmp_path,
        config=config,
        blackboard=bb,
        orchestrator=orch,
    )

    # Empty command usage check
    usage_res: SlashCommandResult = router.execute("/shell")
    assert usage_res.success is False
    assert "Usage: `/shell" in usage_res.markdown_output

    # Execution with command
    res: SlashCommandResult = router.execute("/shell echo 'hello from slash'")
    assert res.success is True
    assert "### Shell Output: `localhost`" in res.markdown_output
    assert "hello from slash" in res.markdown_output

    # Execution via /sh alias
    res_alias: SlashCommandResult = router.execute("/sh echo 'alias test'")
    assert res_alias.success is True
    assert "alias test" in res_alias.markdown_output
