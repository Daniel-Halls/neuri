"""Unit tests for Neuri CLI entrypoint and interactive Textual Chat TUI.

Tests version output, headless execution (-p / --print), slash-command
invocations through CLI, and Textual pilot test interactions (Milestone 6).
"""

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner, Result

from neuri.cli.main import NeuriCLI
from neuri.ui.terminal_chat import NeuriChatApp


@pytest.fixture
def cli_runner() -> CliRunner:
    """Provide a Typer CliRunner fixture for headless CLI testing.

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


# ---------------------------------------------------------------------------
# Test Suite 1: Headless CLI Options
# ---------------------------------------------------------------------------


def test_cli_version_flag(cli_runner: CliRunner) -> None:
    """Test `neuri --version` prints the active version string.

    Parameters
    ------------
    cli_runner: CliRunner
        Typer test runner fixture.

    Returns
    --------
        None: NoneType object
            Asserts exit code 0 and version text.
    """
    cli: NeuriCLI = NeuriCLI()
    res: Result = cli_runner.invoke(cli.cli_app, ["--version"])
    assert res.exit_code == 0
    assert "neuri version 0.1.0" in res.stdout


def test_cli_headless_print_skills(cli_runner: CliRunner) -> None:
    """Test `neuri -p '/skills'` headlessly outputs skills catalog table.

    Parameters
    ------------
    cli_runner: CliRunner
        Typer test runner fixture.

    Returns
    --------
        None: NoneType object
            Asserts exit code 0 and skills catalog content in stdout.
    """
    cli: NeuriCLI = NeuriCLI()
    res: Result = cli_runner.invoke(cli.cli_app, ["-p", "/skills"])
    assert res.exit_code == 0
    assert "Neuroscience Skills Catalog" in res.stdout
    assert "bids-standard" in res.stdout


def test_cli_headless_print_status(
    cli_runner: CliRunner, tmp_path: Path
) -> None:
    """Test `neuri -p '/status'` headlessly outputs system status.

    Parameters
    ------------
    cli_runner: CliRunner
        Typer test runner fixture.
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts exit code 0 and system status content in stdout.
    """
    cli: NeuriCLI = NeuriCLI()
    res: Result = cli_runner.invoke(
        cli.cli_app, ["-p", "/status", "--workspace", str(tmp_path)]
    )
    assert res.exit_code == 0
    assert "Neuri System Status" in res.stdout


def test_cli_headless_print_help(cli_runner: CliRunner) -> None:
    """Test `neuri -p '/help'` headlessly outputs slash command reference.

    Parameters
    ------------
    cli_runner: CliRunner
        Typer test runner fixture.

    Returns
    --------
        None: NoneType object
            Asserts exit code 0 and slash commands in stdout.
    """
    cli: NeuriCLI = NeuriCLI()
    res: Result = cli_runner.invoke(cli.cli_app, ["-p", "/help"])
    assert res.exit_code == 0
    assert "/init" in res.stdout
    assert "/skills" in res.stdout


# ---------------------------------------------------------------------------
# Test Suite 2: Textual Interactive Chat App Pilot Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_textual_chat_app_mounts_and_renders(tmp_path: Path) -> None:
    """Test NeuriChatApp mounts without error and renders initial banner.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts banner, scroll area, and input box exist.
    """
    app: NeuriChatApp = NeuriChatApp(workspace_dir=tmp_path)
    async with app.run_test() as pilot:
        assert app.is_mounted is True
        banner = app.query_one("#workspace-banner")
        assert banner is not None
        assert "Workspace:" in str(banner.render())

        input_box = app.query_one("#prompt-input")
        assert input_box is not None


@pytest.mark.asyncio
async def test_textual_chat_app_submits_slash_command(tmp_path: Path) -> None:
    """Test submitting `/skills` inside NeuriChatApp mounts output message card.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts message card is added to chat scroll area.
    """
    app: NeuriChatApp = NeuriChatApp(workspace_dir=tmp_path)
    async with app.run_test() as pilot:
        input_widget = app.query_one("#prompt-input")
        input_widget.value = "/skills"
        await pilot.press("enter")
        await pilot.pause()

        scroll_area = app.query_one("#chat-scroll")
        children = list(scroll_area.children)
        # Expect welcome card + user turn + assistant turn
        assert len(children) >= 3


@pytest.mark.asyncio
async def test_textual_chat_app_action_clear(tmp_path: Path) -> None:
    """Test action_clear_screen clears all message cards from canvas.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts children are cleared from scroll area.
    """
    app: NeuriChatApp = NeuriChatApp(workspace_dir=tmp_path)
    async with app.run_test() as pilot:
        scroll_area = app.query_one("#chat-scroll")
        assert len(list(scroll_area.children)) > 0

        app.action_clear_screen()
        await pilot.pause()
        assert len(list(scroll_area.children)) == 0
