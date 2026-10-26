"""Unit tests for Neuri installer, ~/.neuri scaffolding, and /install command.

Verifies copying and synchronization of global/, skills/, mcp/, and rules/
from the repository base directory into $HOME/.neuri or custom target locations,
validating CLI integration, slash-command routing, and agent grounding.
"""

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner, Result

from neuri.agents.base_agent import BaseSpecialistAgent
from neuri.cli.main import NeuriCLI
from neuri.core.blackboard import Blackboard
from neuri.core.config import NeuriConfig
from neuri.core.installer import NeuriInstaller
from neuri.core.orchestrator import DAGOrchestrator
from neuri.core.rules import RuleLoader
from neuri.core.slash_commands import SlashCommandResult, SlashCommandRouter


@pytest.fixture
def cli_runner() -> CliRunner:
    """Provide a Typer CliRunner fixture for CLI testing.

    Parameters
    ------------
    None

    Returns
    --------
        CliRunner: CliRunner instance
            Test runner for CLI commands.
    """
    runner: CliRunner = CliRunner()
    return runner


def test_installer_creates_directory_structure(tmp_path: Path) -> None:
    """Test NeuriInstaller scaffolds global, skills, mcp, rules in target.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts all subfolders and base files are created.
    """
    target_dir: Path = tmp_path / ".neuri"
    installer: NeuriInstaller = NeuriInstaller(target_dir=target_dir)

    summary: dict[str, Any] = installer.install(force=False)
    assert summary["target_dir"] == str(target_dir)
    assert "global" in summary["installed"]
    assert "skills" in summary["installed"]
    assert "mcp" in summary["installed"]
    assert "rules" in summary["installed"]

    # Verify global subfolder contains master prompt
    master_prompt_path: Path = target_dir / "global" / "master_prompt.md"
    assert master_prompt_path.is_file()
    content: str = master_prompt_path.read_text(encoding="utf-8")
    assert "Neuri Master System Prompt" in content
    assert "Core Operational Tenets" in content

    # Verify skills catalog and manuals exist
    skills_index: Path = target_dir / "skills" / "index.yaml"
    assert skills_index.is_file()

    # Verify mcp configurations exist
    mcp_config: Path = target_dir / "mcp" / "mcp_servers.json"
    assert mcp_config.is_file()

    # Verify rules directory exists
    rules_dir: Path = target_dir / "rules"
    assert rules_dir.is_dir()

    # Verify config and hosts templates
    assert (target_dir / "hosts.toml").is_file()
    assert (target_dir / "config.toml").is_file()


def test_installer_idempotency_and_force(tmp_path: Path) -> None:
    """Test that installer does not overwrite unless force=True.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts no-op without force, and overwrite with force.
    """
    target_dir: Path = tmp_path / ".neuri"
    installer: NeuriInstaller = NeuriInstaller(target_dir=target_dir)

    # First run: installs sections
    summary1: dict[str, Any] = installer.install(force=False)
    assert len(summary1["installed"]) == 4

    # Second run without force: already installed, so empty list
    summary2: dict[str, Any] = installer.install(force=False)
    assert len(summary2["installed"]) == 0

    # Modify master prompt locally
    prompt_file: Path = target_dir / "global" / "master_prompt.md"
    prompt_file.write_text("Modified prompt", encoding="utf-8")

    # Third run without force: prompt remains modified
    installer.install(force=False)
    assert prompt_file.read_text(encoding="utf-8") == "Modified prompt"

    # Fourth run with force: prompt is overwritten from base
    summary4: dict[str, Any] = installer.install(force=True)
    assert len(summary4["installed"]) == 4
    restored: str = prompt_file.read_text(encoding="utf-8")
    assert "Neuri Master System Prompt" in restored


def test_cli_install_command(
    cli_runner: CliRunner, tmp_path: Path
) -> None:
    """Test running `neuri install --target <path>`.

    Parameters
    ------------
    cli_runner: CliRunner
        Typer test runner fixture.
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts command execution and output.
    """
    cli: NeuriCLI = NeuriCLI()
    target_dir: Path = tmp_path / "custom_install"
    res: Result = cli_runner.invoke(
        cli.cli_app, ["install", "--target", str(target_dir)]
    )

    assert res.exit_code == 0
    assert "Neuri base environment installed successfully into" in res.stdout
    assert (target_dir / "global" / "master_prompt.md").is_file()

    # Re-running without force informs user it is already present
    res_repeat: Result = cli_runner.invoke(
        cli.cli_app, ["install", "--target", str(target_dir)]
    )
    assert res_repeat.exit_code == 0
    assert "already present" in res_repeat.stdout


def test_slash_command_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test /install slash command execution through SlashCommandRouter.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.
    monkeypatch: pytest.MonkeyPatch
        Pytest monkeypatch fixture.

    Returns
    --------
        None: NoneType object
            Asserts slash command results and output markdown.
    """
    fake_home: Path = tmp_path / "fake_home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

    bb: Blackboard = Blackboard(tmp_path / "state.db")
    orch: DAGOrchestrator = DAGOrchestrator(blackboard=bb)
    config: NeuriConfig = NeuriConfig()
    router: SlashCommandRouter = SlashCommandRouter(
        workspace_dir=tmp_path,
        config=config,
        blackboard=bb,
        orchestrator=orch,
    )

    res: SlashCommandResult = router.execute("/install")
    assert res.success is True
    assert "Neuri Base Environment Installed" in res.markdown_output
    assert (fake_home / ".neuri" / "global" / "master_prompt.md").is_file()

    # Test /install on already-installed directory
    res_repeat: SlashCommandResult = router.execute("/install")
    assert res_repeat.success is True
    assert "Already Initialized" in res_repeat.markdown_output

    # Test /install --force
    res_force: SlashCommandResult = router.execute("/install --force")
    assert res_force.success is True
    assert "Neuri Base Environment Installed" in res_force.markdown_output


def test_master_prompt_and_mcp_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test master prompt loading and MCP resolution from installed ~/.neuri.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.
    monkeypatch: pytest.MonkeyPatch
        Pytest monkeypatch fixture.

    Returns
    --------
        None: NoneType object
            Asserts RuleLoader and BaseSpecialistAgent pick up installed assets.
    """
    fake_home: Path = tmp_path / "fake_home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

    # Perform install into fake ~/.neuri
    installer: NeuriInstaller = NeuriInstaller()
    installer.install(force=True)

    # Verify RuleLoader loads master prompt from ~/.neuri/global/master_prompt.md
    loaded_prompt: str = RuleLoader.load_master_prompt(workspace_dir=tmp_path)
    assert "Neuri Master System Prompt" in loaded_prompt
    assert "Core Operational Tenets" in loaded_prompt

    # Verify agent resolves MCP servers from installed mcp/mcp_servers.json
    agent: BaseSpecialistAgent = BaseSpecialistAgent(
        role_name="pipeline_engineer",
        system_prompt="Test agent prompt.",
        skill_ids=["bids_standard"],
        mcp_tools=["remote_worker", "openneuro"],
    )
    mcp_servers: dict[str, dict[str, Any]] = agent.resolve_mcp_servers(
        workspace_dir=tmp_path
    )
    assert "remote_worker" in mcp_servers
    assert "openneuro" in mcp_servers
    assert mcp_servers["remote_worker"]["command"] == "python3"
    assert "neuri_worker.mcp_server" in mcp_servers["remote_worker"]["args"]
