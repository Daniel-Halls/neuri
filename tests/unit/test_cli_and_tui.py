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
    assert "/model" in res.stdout


def test_cli_model_slash_command(
    cli_runner: CliRunner, tmp_path: Path
) -> None:
    """Test /model slash command displays status, lists models, and updates config.

    Parameters
    ------------
    cli_runner: CliRunner
        Typer test runner fixture.
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts /model status, list, update, and reset operations succeed.
    """
    cli: NeuriCLI = NeuriCLI()

    # 1. /model status
    res_status: Result = cli_runner.invoke(
        cli.cli_app, ["-w", str(tmp_path), "-p", "/model"]
    )
    assert res_status.exit_code == 0
    assert "AI Model Configuration" in res_status.stdout

    # 2. /model list
    res_list: Result = cli_runner.invoke(
        cli.cli_app, ["-w", str(tmp_path), "-p", "/model list"]
    )
    assert res_list.exit_code == 0
    assert "Live Available Models Directly from Harnesses" in res_list.stdout

    # 3. /model <name>
    res_set: Result = cli_runner.invoke(
        cli.cli_app, ["-w", str(tmp_path), "-p", "/model gemini-4-argon-medium"]
    )
    assert res_set.exit_code == 0
    assert (
        "Updated global default model to `gemini-4-argon-medium`"
        in res_set.stdout
    )

    # 4. /model <role> <name>
    res_role: Result = cli_runner.invoke(
        cli.cli_app,
        [
            "-w",
            str(tmp_path),
            "-p",
            "/model pipeline_engineer claude-sonnet-5-5-high",
        ],
    )
    assert res_role.exit_code == 0
    assert "Set `pipeline_engineer` to `claude-sonnet-5-5-high`" in res_role.stdout

    # 5. /model reset
    res_reset: Result = cli_runner.invoke(
        cli.cli_app, ["-w", str(tmp_path), "-p", "/model reset"]
    )
    assert res_reset.exit_code == 0
    assert "Restored all harnesses to default models" in res_reset.stdout


def test_cli_model_flag_and_harness_command(
    cli_runner: CliRunner, tmp_path: Path
) -> None:
    """Test CLI --model flag and /harness command with model parameter.

    Parameters
    ------------
    cli_runner: CliRunner
        Typer test runner fixture.
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts --model flag sets active model and /harness sets model.
    """
    cli: NeuriCLI = NeuriCLI()

    # Test /harness with real model
    res_harness: Result = cli_runner.invoke(
        cli.cli_app,
        [
            "-w",
            str(tmp_path),
            "-p",
            "/harness neuroimaging_specialist agy gemini-4-argon-medium",
        ],
    )
    assert res_harness.exit_code == 0
    assert "`gemini-4-argon-medium`" in res_harness.stdout

    # Test --model flag
    res_flag: Result = cli_runner.invoke(
        cli.cli_app,
        [
            "-w",
            str(tmp_path),
            "--model",
            "claude-opus-5-5-high",
            "-p",
            "/model",
        ],
    )
    assert res_flag.exit_code == 0
    assert "claude-opus-5-5-high" in res_flag.stdout


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
    (tmp_path / ".neuri").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".neuri" / "config.toml").write_text(
        '[project]\ntheme = "high_contrast"\n', encoding="utf-8"
    )
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
    (tmp_path / ".neuri").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".neuri" / "config.toml").write_text(
        '[project]\ntheme = "high_contrast"\n', encoding="utf-8"
    )
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
    (tmp_path / ".neuri").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".neuri" / "config.toml").write_text(
        '[project]\ntheme = "high_contrast"\n', encoding="utf-8"
    )
    app: NeuriChatApp = NeuriChatApp(workspace_dir=tmp_path)
    async with app.run_test() as pilot:
        scroll_area = app.query_one("#chat-scroll")
        assert len(list(scroll_area.children)) > 0

        app.action_clear_screen()
        await pilot.pause()
        assert len(list(scroll_area.children)) == 0


@pytest.mark.asyncio
async def test_textual_chat_app_toggle_shell_mode(tmp_path: Path) -> None:
    """Test pressing ctrl+s toggles shell mode and updates input styling.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts mode toggling and widget class updates.
    """
    (tmp_path / ".neuri").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".neuri" / "config.toml").write_text(
        '[project]\ntheme = "high_contrast"\n', encoding="utf-8"
    )
    app: NeuriChatApp = NeuriChatApp(workspace_dir=tmp_path)
    async with app.run_test() as pilot:
        assert app.is_shell_mode is False

        await pilot.press("ctrl+s")
        assert app.is_shell_mode is True

        selector = app.query_one("#machine-selector-bar")
        assert "hidden" not in selector.classes

        input_box = app.query_one("#prompt-input")
        assert "shell-mode" in input_box.classes

        await pilot.press("ctrl+s")
        assert app.is_shell_mode is False
        assert "hidden" in selector.classes


@pytest.mark.asyncio
async def test_textual_chat_app_machine_selection(tmp_path: Path) -> None:
    """Test cycling through target machines using next and prev actions.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts selected machine updates cyclically.
    """
    (tmp_path / ".neuri").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".neuri" / "config.toml").write_text(
        '[project]\ntheme = "high_contrast"\n', encoding="utf-8"
    )
    app: NeuriChatApp = NeuriChatApp(workspace_dir=tmp_path)
    async with app.run_test():
        app.action_toggle_shell_mode()
        app._available_machines = ["localhost", "cluster_node", "gpu_host"]
        app._selected_machine_index = 0
        assert app.selected_machine == "localhost"

        app.action_next_machine()
        assert app.selected_machine == "cluster_node"

        app.action_next_machine()
        assert app.selected_machine == "gpu_host"

        app.action_next_machine()
        assert app.selected_machine == "localhost"

        app.action_prev_machine()
        assert app.selected_machine == "gpu_host"


@pytest.mark.asyncio
async def test_textual_chat_app_submit_shell_command(tmp_path: Path) -> None:
    """Test executing a shell command in shell mode mounts output card.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts command execution and result card mounted on canvas.
    """
    (tmp_path / ".neuri").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".neuri" / "config.toml").write_text(
        '[project]\ntheme = "high_contrast"\n', encoding="utf-8"
    )
    app: NeuriChatApp = NeuriChatApp(workspace_dir=tmp_path)
    async with app.run_test() as pilot:
        app.action_toggle_shell_mode()
        assert app.is_shell_mode is True

        input_widget = app.query_one("#prompt-input")
        input_widget.value = "echo 'hello textual shell'"
        await pilot.press("enter")
        await pilot.pause()

        scroll_area = app.query_one("#chat-scroll")
        children = list(scroll_area.children)
        # welcome card + user shell turn + assistant output turn
        assert len(children) >= 3


@pytest.mark.asyncio
async def test_textual_chat_app_theme_slash_command(tmp_path: Path) -> None:
    """Test typing /theme dark in TUI dynamically updates active theme.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts application theme switches to dark upon slash command submission.
    """
    (tmp_path / ".neuri").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".neuri" / "config.toml").write_text(
        '[project]\ntheme = "high_contrast"\n', encoding="utf-8"
    )
    app: NeuriChatApp = NeuriChatApp(workspace_dir=tmp_path)
    async with app.run_test() as pilot:
        # Default theme is high_contrast
        assert app.theme == "high_contrast"

        # Type /theme dark
        input_widget = app.query_one("#prompt-input")
        input_widget.value = "/theme dark"
        await pilot.press("enter")
        await pilot.pause()

        # Check theme updated to dark
        assert app.theme == "dark"

        # Type /theme high_contrast
        input_widget.value = "/theme high_contrast"
        await pilot.press("enter")
        await pilot.pause()

        # Check theme switched back to high_contrast
        assert app.theme == "high_contrast"


# ---------------------------------------------------------------------------
# Test Suite 3: Real-Time Telemetry and Feedback Streaming
# ---------------------------------------------------------------------------


def test_live_feedback_card_composition_and_updates() -> None:
    """Test LiveFeedbackCard lifecycle, thinking append, and content updates.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts widget state mutations and text updates.
    """
    from neuri.ui.terminal_chat import LiveFeedbackCard

    card: LiveFeedbackCard = LiveFeedbackCard(node_id="node_bet_01")
    assert card._node_id == "node_bet_01"
    assert card._status_text == "Dispatching to harness..."

    # Test status update
    card.set_status("Running FSL BET brain extraction...")
    assert card._status_text == "Running FSL BET brain extraction..."

    # Test thinking delta accumulation
    card.append_thinking("Analyzing brain volume shape...")
    card.append_thinking(" Fractional intensity set to 0.5.")
    assert len(card._thinking_chunks) == 2
    assert "".join(card._thinking_chunks) == (
        "Analyzing brain volume shape... Fractional intensity set to 0.5."
    )

    # Test content delta accumulation
    card.append_content("Skull stripping ")
    card.append_content("completed successfully.")
    assert len(card._content_chunks) == 2
    assert "".join(card._content_chunks) == (
        "Skull stripping completed successfully."
    )

    # Verify compose() runs cleanly without NameError or missing dependencies
    composed_widgets = list(card.compose())
    assert len(composed_widgets) >= 3


def test_session_engine_forwards_content_delta_and_tools(
    tmp_path: Path,
) -> None:
    """Test session engine dispatches ASSISTANT_CHUNK and TOOL_CALL_UPDATE.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts events reach subscriber callbacks with typed payloads.
    """
    from neuri.core.schemas import SessionEvent, SessionEventType, TelemetryEvent
    from neuri.core.session import NeuriSessionEngine

    engine: NeuriSessionEngine = NeuriSessionEngine(workspace_dir=tmp_path)
    captured_events: list[SessionEvent] = []

    engine.subscribe(lambda ev: captured_events.append(ev))

    # 1. Forward content delta
    telem_content: TelemetryEvent = TelemetryEvent(
        event_id="evt-content-01",
        workflow_id="wf-stream-01",
        node_id="node-stream-01",
        harness_id="agy",
        event_type="content_delta",
        content_text="Streaming token chunk.",
    )
    engine._forward_telemetry(telem_content)

    assert len(captured_events) == 1
    assert captured_events[0].event_type == SessionEventType.ASSISTANT_CHUNK
    assert (
        captured_events[0].payload.get("content_delta")
        == "Streaming token chunk."
    )

    # 2. Forward tool lifecycle
    telem_tool: TelemetryEvent = TelemetryEvent(
        event_id="evt-tool-01",
        workflow_id="wf-stream-01",
        node_id="node-stream-01",
        harness_id="agy",
        event_type="tool_lifecycle",
        tool_name="fsl_bet",
        tool_host="localhost",
        tool_status="completed",
        duration_ms=420,
    )
    engine._forward_telemetry(telem_tool)

    assert len(captured_events) == 2
    assert captured_events[1].event_type == SessionEventType.TOOL_CALL_UPDATE
    assert captured_events[1].payload.get("tool_name") == "fsl_bet"
    assert captured_events[1].payload.get("duration_ms") == 420

    # 3. Forward raw stream
    telem_raw: TelemetryEvent = TelemetryEvent(
        event_id="evt-raw-01",
        workflow_id="wf-stream-01",
        node_id="node-stream-01",
        harness_id="agy",
        event_type="raw_stream",
        raw_text="Node node-01 started running on agy",
    )
    engine._forward_telemetry(telem_raw)

    assert len(captured_events) == 3
    assert captured_events[2].event_type == SessionEventType.STATUS_UPDATE
    assert (
        captured_events[2].payload.get("raw_text")
        == "Node node-01 started running on agy"
    )


@pytest.mark.asyncio
async def test_textual_chat_app_mounts_live_feedback_card(
    tmp_path: Path,
) -> None:
    """Test mounting LiveFeedbackCard in NeuriChatApp scroll area.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts widget mounts and renders without exceptions.
    """
    from neuri.ui.terminal_chat import LiveFeedbackCard

    app: NeuriChatApp = NeuriChatApp(workspace_dir=tmp_path)
    async with app.run_test() as pilot:
        scroll_area = app.query_one("#chat-scroll")
        card: LiveFeedbackCard = LiveFeedbackCard(node_id="node_test_01")
        await scroll_area.mount(card)
        await pilot.pause()
        assert card.is_mounted is True
        assert app.query_one(LiveFeedbackCard) is not None


def test_telemetry_bar_renders_harness_and_model() -> None:
    """Test TelemetryBar renders Harness: and Model: next to each other.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts Harness and Model labels and values are present in Content.
    """
    from neuri.ui.terminal_chat import TelemetryBar

    bar: TelemetryBar = TelemetryBar(
        harness_id="ollama",
        model_id="gemma4:26b",
    )
    rendered = bar.render()
    plain_text: str = rendered.plain
    assert "Harness: " in plain_text
    assert "ollama" in plain_text
    assert "Model: " in plain_text
    assert "gemma4:26b" in plain_text

    bar.set_harness_id("agy")
    bar.set_model_id("gemini-4-argon-medium")
    rendered2 = bar.render()
    assert "agy" in rendered2.plain
    assert "gemini-4-argon-medium" in rendered2.plain


def test_uniform_harness_and_model_across_all_roles(tmp_path: Path) -> None:
    """Test harness and model settings apply uniformly across all roles.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts all roles reflect identical harness and model.
    """
    from neuri.core.session import NeuriSessionEngine

    engine: NeuriSessionEngine = NeuriSessionEngine(
        workspace_dir=tmp_path,
        harness="ollama",
        model="kimi-k2.7-code:cloud",
    )
    assert engine.harness == "ollama"
    assert engine.model == "kimi-k2.7-code:cloud"
    for r_cfg in engine.config.harness_routing.values():
        assert r_cfg.harness == "ollama"
        assert r_cfg.model == "kimi-k2.7-code:cloud"


@pytest.mark.asyncio
async def test_dynamic_model_validation_and_ui_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test dynamic model resolution, validation against harness, and UI sync.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.
    monkeypatch: pytest.MonkeyPatch
        Pytest monkeypatch fixture.

    Returns
    --------
        None: NoneType object
            Asserts invalid models are rejected and valid models update UI.
    """
    (tmp_path / ".neuri").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".neuri" / "config.toml").write_text(
        '[project]\ntheme = "high_contrast"\ndefault_harness = "agy"\n',
        encoding="utf-8",
    )
    app: NeuriChatApp = NeuriChatApp(workspace_dir=tmp_path)
    monkeypatch.setattr(
        app._engine._orchestrator.registry,
        "get_models_for_harness",
        lambda h: (
            ["gemini-4-argon-medium", "claude-opus-5-5-high"]
            if h == "agy"
            else ["gemma4:26b", "kimi-k2.7-code:cloud"]
        ),
    )
    async with app.run_test() as pilot:
        # 1. Switch to valid model via /model
        input_widget = app.query_one("#prompt-input")
        input_widget.value = "/model claude-opus-5-5-high"
        await pilot.press("enter")
        await pilot.pause()

        assert app._engine.model == "claude-opus-5-5-high"
        assert app._telemetry_bar.model_id == "claude-opus-5-5-high"
        banner_txt: str = str(app.query_one("#workspace-banner").render())
        assert "harness agy" in banner_txt
        assert "model claude-opus-5-5-high" in banner_txt

        # 2. Reject non-existent model on agy
        input_widget.value = "/model non-existent-fake-model"
        await pilot.press("enter")
        await pilot.pause()
        assert app._engine.model == "claude-opus-5-5-high"

        # 3. Switch harness to ollama -> auto-resolves first ollama model
        input_widget.value = "/harness ollama"
        await pilot.press("enter")
        await pilot.pause()
        assert app._engine.harness == "ollama"
        assert app._engine.model == "gemma4:26b"
        assert app._telemetry_bar.harness_id == "ollama"
        assert app._telemetry_bar.model_id == "gemma4:26b"
        banner_txt2: str = str(app.query_one("#workspace-banner").render())
        assert "harness ollama" in banner_txt2
        assert "model gemma4:26b" in banner_txt2
