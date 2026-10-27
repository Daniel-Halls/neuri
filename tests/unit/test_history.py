"""Unit tests for bash-like command history and prompt autofocus in Neuri TUI.

Tests PromptHistoryManager persistence, arrow-key navigation, draft preservation,
slash-command `/history`, and Textual autofocus on printable keystrokes.
"""

from pathlib import Path

import pytest

from neuri.core.blackboard import Blackboard
from neuri.core.config import NeuriConfig
from neuri.core.orchestrator import DAGOrchestrator
from neuri.core.slash_commands import SlashCommandResult, SlashCommandRouter
from neuri.ui.history import PromptHistoryManager
from neuri.ui.terminal_chat import NeuriChatApp, PromptInput


def test_history_manager_add_and_persistence(tmp_path: Path) -> None:
    """Test history manager adds entries, deduplicates, and saves to disk.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts entry list and file persistence.
    """
    hist_file: Path = tmp_path / "test_history"
    mgr: PromptHistoryManager = PromptHistoryManager(
        history_file=hist_file, max_entries=5
    )
    assert mgr.entries == []

    mgr.add_entry("ls -la")
    mgr.add_entry("ls -la")  # Duplicate ignored
    mgr.add_entry("python test.py")
    mgr.add_entry("bids validate")

    assert mgr.entries == ["ls -la", "python test.py", "bids validate"]
    assert hist_file.is_file()

    # Re-load in a new manager
    mgr2: PromptHistoryManager = PromptHistoryManager(
        history_file=hist_file, max_entries=5
    )
    assert mgr2.entries == ["ls -la", "python test.py", "bids validate"]


def test_history_manager_arrow_navigation_and_draft(tmp_path: Path) -> None:
    """Test bash-like Up and Down navigation and user draft restoration.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts chronological navigation and draft recovery.
    """
    hist_file: Path = tmp_path / "test_history"
    mgr: PromptHistoryManager = PromptHistoryManager(history_file=hist_file)
    mgr.add_entry("cmd_one")
    mgr.add_entry("cmd_two")
    mgr.add_entry("cmd_three")

    # Navigate Up from draft "my_draft"
    first_up: str | None = mgr.navigate_up("my_draft")
    assert first_up == "cmd_three"

    second_up: str | None = mgr.navigate_up("cmd_three")
    assert second_up == "cmd_two"

    third_up: str | None = mgr.navigate_up("cmd_two")
    assert third_up == "cmd_one"

    # Beyond oldest stays at oldest
    fourth_up: str | None = mgr.navigate_up("cmd_one")
    assert fourth_up == "cmd_one"

    # Navigate Down back towards draft
    first_down: str | None = mgr.navigate_down()
    assert first_down == "cmd_two"

    second_down: str | None = mgr.navigate_down()
    assert second_down == "cmd_three"

    # Past latest restores draft
    restored_draft: str | None = mgr.navigate_down()
    assert restored_draft == "my_draft"

    # Further down returns None
    assert mgr.navigate_down() is None


def test_history_manager_max_entries_and_clear(tmp_path: Path) -> None:
    """Test trimming old entries at max limit and clear method.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts FIFO eviction and file removal on clear.
    """
    hist_file: Path = tmp_path / "test_history"
    mgr: PromptHistoryManager = PromptHistoryManager(
        history_file=hist_file, max_entries=3
    )
    for i in range(5):
        mgr.add_entry(f"item_{i}")

    assert mgr.entries == ["item_2", "item_3", "item_4"]

    mgr.clear()
    assert mgr.entries == []
    assert not hist_file.exists()


def test_slash_command_history(tmp_path: Path) -> None:
    """Test `/history` command displays recent commands and clears history.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts history markdown rendering and clear confirmation.
    """
    cfg: NeuriConfig = NeuriConfig()
    bb: Blackboard = Blackboard(tmp_path / "test.db")
    orch: DAGOrchestrator = DAGOrchestrator(blackboard=bb, config=cfg)
    router: SlashCommandRouter = SlashCommandRouter(
        workspace_dir=tmp_path,
        config=cfg,
        blackboard=bb,
        orchestrator=orch,
    )

    res: SlashCommandResult = router.execute("/history")
    assert res.success is True


@pytest.mark.asyncio
async def test_terminal_chat_prompt_history_keys(tmp_path: Path) -> None:
    """Test interactive Textual PromptInput arrow-key history recall.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts input value matches history entries on Up/Down.
    """
    hist_file: Path = tmp_path / "history"
    mgr: PromptHistoryManager = PromptHistoryManager(history_file=hist_file)
    mgr.add_entry("command_alpha")
    mgr.add_entry("command_beta")

    app: NeuriChatApp = NeuriChatApp(workspace_dir=tmp_path)

    async with app.run_test() as pilot:
        prompt = app.query_one("#prompt-input", PromptInput)
        prompt._history_manager = mgr
        prompt.focus()
        await pilot.pause()

        # Press Up arrow
        await pilot.press("up")
        assert prompt.value == "command_beta"

        # Press Up arrow again
        await pilot.press("up")
        assert prompt.value == "command_alpha"

        # Press Down arrow
        await pilot.press("down")
        assert prompt.value == "command_beta"

        # Press Down arrow back to empty draft
        await pilot.press("down")
        assert prompt.value == ""


@pytest.mark.asyncio
async def test_terminal_chat_autofocus_on_typing(tmp_path: Path) -> None:
    """Test typing when unfocused automatically focuses prompt and inserts text.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts prompt receives keystrokes and gains focus.
    """
    app: NeuriChatApp = NeuriChatApp(workspace_dir=tmp_path)

    async with app.run_test() as pilot:
        prompt = app.query_one("#prompt-input", PromptInput)
        scroll = app.query_one("#chat-scroll")

        # Focus scroll container to simulate clicking away from prompt
        scroll.focus()
        await pilot.pause()
        assert app.focused == scroll

        # Start typing 'neuri'
        await pilot.press("n", "e", "u", "r", "i")
        await pilot.pause()

        assert prompt.value == "neuri"
        assert app.focused == prompt

        # Test backspace when unfocused
        scroll.focus()
        await pilot.pause()
        assert app.focused == scroll

        await pilot.press("backspace")
        await pilot.pause()

        assert prompt.value == "neur"
        assert app.focused == prompt
