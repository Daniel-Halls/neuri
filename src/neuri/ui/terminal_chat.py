"""Interactive Terminal Chat Interface for Neuri (Textual TUI).

Implements the agy-style interactive terminal chat window launched via `neuri`.
Provides a rich scrollable canvas, slash-command autocompletion, collapsible
reasoning drawers, and live telemetry status bars.
"""

import asyncio
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import (
    Collapsible,
    Footer,
    Header,
    Input,
    Label,
    Markdown,
    Static,
)

from neuri.core.schemas import ChatRole, ChatTurn, SessionEvent, SessionEventType
from neuri.core.session import NeuriSessionEngine
from neuri.remote.shell_executor import (
    ShellCommandExecutor,
    ShellExecutionResult,
)
from neuri.ui.history import PromptHistoryManager
from neuri.ui.theme import NeuriTheme, NeuriThemeManager


class MessageCard(Static):
    """Visual message card displaying user or assistant content in chat canvas.

    Parameters
    ------------
    turn: ChatTurn
        Chat turn model to display.

    Returns
    --------
        MessageCard: MessageCard instance
            Constructed message widget card.
    """

    def __init__(self, turn: ChatTurn) -> None:
        """Initialize message card.

        Parameters
        ------------
        turn: ChatTurn
            The chat turn data model.

        Returns
        --------
            None: NoneType object
                Initializes widget state.
        """
        super().__init__()
        self._turn: ChatTurn = turn

    def compose(self) -> ComposeResult:
        """Compose child widgets inside the message card.

        Parameters
        ------------
        None

        Returns
        --------
            ComposeResult: ComposeResult generator
                Yields header label and Markdown body widgets.
        """
        if self._turn.role == ChatRole.USER:
            yield Label(
                f"❯ ({self._turn.timestamp.strftime('%H:%M:%S')})",
                classes="user-header",
            )
            yield Static(self._turn.content, classes="user-body")
        else:
            yield Label(
                f">> Neuri",
                classes="assistant-header",
            )
            if self._turn.thinking_trace:
                with Collapsible(title="Reasoning Trace", collapsed=True):
                    yield Static(
                        self._turn.thinking_trace, classes="thinking-text"
                    )
            yield Markdown(self._turn.content, classes="assistant-body")


class ComputeSidebar(VerticalScroll):
    """Sidebar widget displaying attached machines and active remote jobs.

    Parameters
    ------------
    None

    Returns
    --------
        ComputeSidebar: ComputeSidebar instance
            Constructed compute sidebar widget.
    """

    def __init__(self) -> None:
        """Initialize compute sidebar widget.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Initializes widget state.
        """
        super().__init__(id="compute-sidebar")
        self._content: Static = Static(
            "Loading compute fabric...", id="compute-sidebar-content"
        )
        self._last_machines_data: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        """Compose child widgets inside sidebar.

        Parameters
        ------------
        None

        Returns
        --------
            ComposeResult: ComposeResult generator
                Yields header label and content widget.
        """
        yield Label("Machines [F2] ", id="compute-sidebar-title")
        yield self._content

    def _get_theme(self) -> NeuriTheme:
        """Resolve active theme model from parent application context.

        Parameters
        ------------
        None

        Returns
        --------
            NeuriTheme: NeuriTheme instance
                Current active theme object.
        """
        try:
            chat_app: Any = self.app
            if chat_app is not None and hasattr(chat_app, "active_neuri_theme"):
                return chat_app.active_neuri_theme
        except Exception:
            pass
        return NeuriThemeManager().get_high_contrast_theme()

    def update_machines(
        self,
        machines_data: list[dict[str, Any]],
        theme: NeuriTheme | None = None,
    ) -> None:
        """Render formatted machine status and active jobs into sidebar.

        Parameters
        ------------
        machines_data: list[dict[str, Any]]
            List of machine health and job dictionaries.
        theme: NeuriTheme | None
            Optional explicit theme model. Defaults to None.

        Returns
        --------
            None: NoneType object
                Updates text inside sidebar content widget.
        """
        self._last_machines_data = machines_data
        active_theme: NeuriTheme = (
            theme if theme is not None else self._get_theme()
        )
        if not machines_data:
            self._content.update(
                Text(
                    "No attached machines.\nUse /remote bootstrap <host>",
                    style=f"{active_theme.muted}",
                )
            )
            return

        txt: Text = Text()
        for idx, machine in enumerate(machines_data):
            if idx > 0:
                txt.append(
                    "\n" + "─" * 26 + "\n", style=f"{active_theme.border}"
                )
            host_name: str = str(machine.get("host", "unknown"))
            online: bool = bool(machine.get("online", False))
            if online:
                txt.append("● ", style=f"bold {active_theme.success}")
                txt.append(
                    f"{host_name}\n", style=f"bold {active_theme.foreground}"
                )
                cores: int = int(machine.get("cpu_count", 1))
                load_arr: list[float] = machine.get("load_avg", [0.0, 0.0, 0.0])
                load_s: str = f"{load_arr[0]:.2f}" if load_arr else "-"
                txt.append(
                    f"  CPUs: {cores} │ Load: {load_s}\n",
                    style=f"{active_theme.accent}",
                )

                n_jobs: list[dict[str, Any]] = machine.get("neuri_jobs", [])
                s_jobs: list[dict[str, Any]] = machine.get("slurm_jobs", [])
                total_jobs: int = len(n_jobs) + len(s_jobs)
                if total_jobs == 0:
                    txt.append("  Jobs: Idle\n", style=f"{active_theme.muted}")
                else:
                    for nj in n_jobs:
                        st: str = str(nj.get("state", "RUNNING"))
                        style_tag: str = (
                            active_theme.success
                            if st == "RUNNING"
                            else active_theme.warning
                        )
                        txt.append(
                            f"  ▶ [Neuri] {nj.get('job_id')}: {st}\n",
                            style=style_tag,
                        )
                    for sj in s_jobs:
                        st = str(sj.get("state", "R"))
                        style_tag = (
                            active_theme.success
                            if st in ("R", "RUNNING")
                            else active_theme.warning
                        )
                        txt.append(
                            f"  ▶ [Slurm] #{sj.get('slurm_job_id')}: {st}\n",
                            style=style_tag,
                        )
            else:
                txt.append("○ ", style=f"bold {active_theme.error}")
                txt.append(
                    f"{host_name} (Offline)\n", style=f"{active_theme.error}"
                )

        try:
            self._content.update(txt)
        except Exception:
            pass

    def refresh_theme(self, theme: NeuriTheme | None = None) -> None:
        """Re-render content with the newly activated theme palette.

        Parameters
        ------------
        theme: NeuriTheme | None
            Optional updated theme model. Defaults to None.

        Returns
        --------
            None: NoneType object
                Re-renders sidebar content.
        """
        if self._last_machines_data:
            self.update_machines(self._last_machines_data, theme=theme)


class MachineSelectorBar(Static):
    """Bar displaying active target machine and selector pills for shell mode.

    Parameters
    ------------
    None

    Returns
    --------
        MachineSelectorBar: MachineSelectorBar instance
            Constructed selector bar widget.
    """

    def __init__(self) -> None:
        """Initialize machine selector bar.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Initializes widget state.
        """
        super().__init__(id="machine-selector-bar", classes="hidden")
        self._machines: list[str] = ["localhost"]
        self._current_index: int = 0

    def _get_theme(self) -> NeuriTheme:
        """Resolve active theme model from parent application context.

        Parameters
        ------------
        None

        Returns
        --------
            NeuriTheme: NeuriTheme instance
                Current active theme object.
        """
        try:
            chat_app: Any = self.app
            if chat_app is not None and hasattr(chat_app, "active_neuri_theme"):
                return chat_app.active_neuri_theme
        except Exception:
            pass
        return NeuriThemeManager().get_high_contrast_theme()

    def update_selection(
        self, machines: list[str], current_index: int
    ) -> None:
        """Update machine list and active selection highlighting.

        Parameters
        ------------
        machines: list[str]
            List of available machine aliases.
        current_index: int
            Zero-based index of the currently selected machine.

        Returns
        --------
            None: NoneType object
                Renders updated rich text with highlighted machine pill.
        """
        self._machines = machines if machines else ["localhost"]
        self._current_index = max(
            0, min(current_index, len(self._machines) - 1)
        )
        self._render_bar()

    def _render_bar(self, theme: NeuriTheme | None = None) -> None:
        """Render selector bar using active theme palette.

        Parameters
        ------------
        theme: NeuriTheme | None
            Optional explicit theme model. Defaults to None.

        Returns
        --------
            None: NoneType object
                Updates widget display.
        """
        active_theme: NeuriTheme = (
            theme if theme is not None else self._get_theme()
        )
        txt: Text = Text()
        txt.append("SHELL ", style=f"bold {active_theme.success}")
        txt.append("│ Target: ", style=f"bold {active_theme.accent}")
        selected_name: str = self._machines[self._current_index]
        txt.append(f"◀ {selected_name} ▶ ", style=f"bold {active_theme.warning}")
        txt.append("│ Machines: ", style=f"{active_theme.muted}")

        for idx, machine_name in enumerate(self._machines):
            if idx == self._current_index:
                txt.append(
                    f" [● {machine_name}] ",
                    style=(
                        f"bold {active_theme.selection_fg} "
                        f"on {active_theme.selection_bg}"
                    ),
                )
            else:
                txt.append(f" ○ {machine_name} ", style=f"{active_theme.muted}")

        txt.append(
            " │ (←/→ or ↑/↓: select │ Ctrl+S: exit)",
            style=f"italic {active_theme.accent}",
        )
        try:
            self.update(txt)
        except Exception:
            pass

    def refresh_theme(self, theme: NeuriTheme | None = None) -> None:
        """Re-render selector bar with newly activated theme palette.

        Parameters
        ------------
        theme: NeuriTheme | None
            Optional updated theme model. Defaults to None.

        Returns
        --------
            None: NoneType object
                Re-renders selector bar display.
        """
        self._render_bar(theme=theme)


class PromptInput(Input):
    """Custom input widget providing bash-like history and shell machine switching.

    Parameters
    ------------
    value: str | None
        Initial text value. Defaults to None.
    placeholder: str
        Initial placeholder text. Defaults to empty string.
    id: str | None
        Widget ID. Defaults to None.
    classes: str | None
        CSS classes. Defaults to None.
    disabled: bool
        Whether widget is disabled. Defaults to False.
    select_on_focus: bool
        Whether to select all text on focus. Defaults to False.
    history_manager: PromptHistoryManager | None
        Optional history manager instance. Defaults to None.

    Returns
    --------
        PromptInput: PromptInput instance
            Constructed prompt input widget.
    """

    def __init__(
        self,
        value: str | None = None,
        placeholder: str = "",
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        select_on_focus: bool = False,
        history_manager: PromptHistoryManager | None = None,
    ) -> None:
        """Initialize PromptInput with optional history manager.

        Parameters
        ------------
        value: str | None
            Initial text value. Defaults to None.
        placeholder: str
            Initial placeholder text. Defaults to empty string.
        id: str | None
            Widget ID. Defaults to None.
        classes: str | None
            CSS classes. Defaults to None.
        disabled: bool
            Whether widget is disabled. Defaults to False.
        select_on_focus: bool
            Whether to select all text on focus. Defaults to False.
        history_manager: PromptHistoryManager | None
            Optional history manager instance. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes prompt widget attributes.
        """
        super().__init__(
            value=value,
            placeholder=placeholder,
            id=id,
            classes=classes,
            disabled=disabled,
            select_on_focus=select_on_focus,
        )
        self._history_manager: PromptHistoryManager | None = history_manager

    def _get_history_manager(self) -> PromptHistoryManager | None:
        """Resolve active history manager from direct reference or parent app.

        Parameters
        ------------
        None

        Returns
        --------
            PromptHistoryManager | None: optional manager instance
                Active history manager or None if unattached.
        """
        if self._history_manager is not None:
            return self._history_manager
        try:
            chat_app: Any = self.app
            if chat_app is not None and hasattr(chat_app, "history_manager"):
                manager: PromptHistoryManager = chat_app.history_manager
                return manager
        except Exception:
            pass
        return None

    async def _on_key(self, event: events.Key) -> None:
        """Handle key events for bash-like history and shell machine navigation.

        Parameters
        ------------
        event: events.Key
            Key event data.

        Returns
        --------
            None: NoneType object
                Navigates history, machines, or delegates to standard text input.
        """
        chat_app: Any = self.app

        # Up and Down arrows: Navigate bash-like command and prompt history
        if event.key in ("up", "down"):
            history: PromptHistoryManager | None = self._get_history_manager()
            if history is not None:
                if event.key == "up":
                    nav_val: str | None = history.navigate_up(self.value)
                    if nav_val is not None:
                        self.value = nav_val
                        self.cursor_position = len(nav_val)
                        event.prevent_default()
                        event.stop()
                        return
                elif event.key == "down":
                    nav_val = history.navigate_down()
                    if nav_val is not None:
                        self.value = nav_val
                        self.cursor_position = len(nav_val)
                        event.prevent_default()
                        event.stop()
                        return

        # In shell mode, switch machines via Left/Right arrows when prompt is empty
        if chat_app is not None and getattr(chat_app, "is_shell_mode", False):
            if event.key in ("left", "right") and not self.value:
                event.prevent_default()
                event.stop()
                if event.key == "left":
                    chat_app.action_prev_machine()
                else:
                    chat_app.action_next_machine()
                return

        await super()._on_key(event)


class TelemetryBar(Static):
    """Status bar widget displaying live tokens, cost, and harness routing.

    Parameters
    ------------
    harness_id: str
        Default harness identifier. Defaults to 'agy'.

    Returns
    --------
        TelemetryBar: TelemetryBar instance
            Constructed telemetry bar widget.
    """

    tokens_count: reactive[int] = reactive(0)
    cost_usd: reactive[float] = reactive(0.0)
    status_text: reactive[str] = reactive("Ready")
    machines_summary: reactive[str] = reactive("0 online")

    def __init__(
        self,
        harness_id: str = "agy",
        theme: NeuriTheme | None = None,
    ) -> None:
        """Initialize telemetry status bar.

        Parameters
        ------------
        harness_id: str
            Harness identifier string. Defaults to 'agy'.
        theme: NeuriTheme | None
            Optional theme override model. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes widget attributes.
        """
        super().__init__()
        self._harness_id: str = harness_id
        self._custom_theme: NeuriTheme | None = theme

    def set_theme(self, theme: NeuriTheme) -> None:
        """Set an explicit theme override for telemetry bar rendering.

        Parameters
        ------------
        theme: NeuriTheme
            New theme model to apply.

        Returns
        --------
            None: NoneType object
                Updates widget theme state.
        """
        self._custom_theme = theme
        try:
            self.refresh()
        except Exception:
            pass

    def _get_theme(self) -> NeuriTheme:
        """Resolve active theme model from parent application context.

        Parameters
        ------------
        None

        Returns
        --------
            NeuriTheme: NeuriTheme instance
                Current active theme object.
        """
        if self._custom_theme is not None:
            return self._custom_theme
        try:
            chat_app: Any = self.app
            if chat_app is not None and hasattr(chat_app, "active_neuri_theme"):
                return chat_app.active_neuri_theme
        except Exception:
            pass
        fallback: NeuriTheme = NeuriThemeManager().get_high_contrast_theme()
        return fallback

    def render(self) -> Text:
        """Render formatted rich text for telemetry footer.

        Parameters
        ------------
        None

        Returns
        --------
            Text: Text object
                Rich text display styled by active theme.
        """
        theme: NeuriTheme = self._get_theme()
        label_style: str = f"bold {theme.accent}"
        txt: Text = Text()
        txt.append(" Harness: ", style=label_style)
        txt.append(f"{self._harness_id} ", style=f"{theme.success}")
        txt.append("│ Machines: ", style=label_style)
        txt.append(f"{self.machines_summary} ", style=f"{theme.success}")
        txt.append("│ Tokens: ", style=label_style)
        txt.append(f"{self.tokens_count:,} ", style=f"{theme.tokens}")
        txt.append("│ Cost: ", style=label_style)
        txt.append(f"${self.cost_usd:.4f} ", style=f"{theme.cost}")
        txt.append("│ Status: ", style=label_style)
        txt.append(f"{self.status_text}", style=f"bold {theme.success}")
        return txt

    def refresh_theme(self, theme: NeuriTheme | None = None) -> None:
        """Re-render telemetry bar with newly activated theme palette.

        Parameters
        ------------
        theme: NeuriTheme | None
            Optional updated theme model. Defaults to None.

        Returns
        --------
            None: NoneType object
                Refreshes telemetry widget display.
        """
        try:
            self.refresh()
        except Exception:
            pass


class NeuriChatApp(App[None]):
    """Textual interactive chat application for Neuri.

    Launched when the user executes `neuri` in terminal. Houses the scrollable
    chat canvas, slash command input box, and live telemetry bar.

    Parameters
    ------------
    workspace_dir: Path | None
        Target workspace root directory. Defaults to Path.cwd().
    session_engine: NeuriSessionEngine | None
        Optional pre-configured session engine. Defaults to None.

    Returns
    --------
        NeuriChatApp: NeuriChatApp instance
            Constructed Textual application.
    """

    TITLE = "Neuri"
    SUB_TITLE = "The friendly neuroscientist"

    CSS = """
    Screen {
        background: $background;
        color: $foreground;
    }
    #workspace-banner {
        dock: top;
        height: 2;
        background: $surface;
        color: $foreground;
        padding: 0 1;
        border-bottom: solid $border;
    }
    #main-horizontal {
        height: 1fr;
    }
    #chat-scroll {
        width: 1fr;
        height: 100%;
        padding: 1 2;
    }
    #compute-sidebar {
        width: 34;
        height: 100%;
        background: $panel;
        border-left: solid $border;
        padding: 0 1;
    }
    #compute-sidebar.hidden {
        display: none;
    }
    #compute-sidebar-title {
        color: $primary;
        text-style: bold;
        background: $surface;
        padding: 0 1;
        margin-bottom: 1;
        width: 100%;
    }
    #compute-sidebar-content {
        color: $foreground;
    }
    #input-container {
        dock: bottom;
        height: auto;
        padding: 0 1 1 1;
        background: $background;
    }
    #machine-selector-bar {
        height: 1;
        margin-bottom: 0;
        padding: 0 1;
        background: $surface;
        color: $foreground;
    }
    #machine-selector-bar.hidden {
        display: none;
    }
    Input {
        border: tall $border;
        background: $surface;
        color: $foreground;
    }
    Input:focus {
        border: tall $accent;
    }
    Input.shell-mode {
        border: tall $success;
    }
    Input.shell-mode:focus {
        border: tall $success;
    }
    #telemetry-bar {
        dock: bottom;
        height: 1;
        background: $surface;
        color: $foreground;
        padding: 0 1;
    }
    .user-header {
        color: $primary;
        text-style: bold;
        margin-top: 1;
    }
    .user-body {
        margin-left: 2;
        margin-bottom: 1;
        color: $foreground;
    }
    .assistant-header {
        color: $secondary;
        text-style: bold;
        margin-top: 1;
    }
    .assistant-body {
        margin-left: 2;
        margin-bottom: 1;
    }
    .thinking-text {
        color: $foreground;
        text-style: italic;
        padding: 1;
        background: $surface;
    }
    """

    BINDINGS: list[Binding] = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+q", "quit", "Quit", show=False),
        Binding("ctrl+l", "clear_screen", "Clear", show=True),
        Binding("ctrl+s", "toggle_shell_mode", "Shell Mode", show=True),
        Binding("f2", "toggle_sidebar", "Machines", show=True),
        Binding("ctrl+b", "toggle_sidebar", "Machines", show=False),
    ]

    def __init__(
        self,
        workspace_dir: Path | None = None,
        session_engine: NeuriSessionEngine | None = None,
    ) -> None:
        """Initialize Neuri Textual chat application.

        Parameters
        ------------
        workspace_dir: Path | None
            Workspace directory. Defaults to None (cwd).
        session_engine: NeuriSessionEngine | None
            Session engine instance. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes application state.
        """
        super().__init__()
        self._workspace_dir: Path = (
            workspace_dir if workspace_dir is not None else Path.cwd()
        )
        self._engine: NeuriSessionEngine = (
            session_engine
            if session_engine is not None
            else NeuriSessionEngine(workspace_dir=self._workspace_dir)
        )
        self._telemetry_bar: TelemetryBar = TelemetryBar()
        self._compute_sidebar: ComputeSidebar = ComputeSidebar()
        self._is_shell_mode: bool = False
        self._available_machines: list[str] = ["localhost"]
        self._selected_machine_index: int = 0
        self._shell_executor: ShellCommandExecutor = ShellCommandExecutor(
            workspace_dir=self._workspace_dir
        )
        self._machine_selector_bar: MachineSelectorBar = MachineSelectorBar()
        self._theme_manager: NeuriThemeManager = NeuriThemeManager(
            workspace_dir=self._workspace_dir
        )
        self._history_manager: PromptHistoryManager = PromptHistoryManager()
        self._engine.subscribe(self._handle_session_event)

    @property
    def history_manager(self) -> PromptHistoryManager:
        """Return the active command and prompt history manager.

        Parameters
        ------------
        None

        Returns
        --------
            PromptHistoryManager: PromptHistoryManager instance
                Application command history manager.
        """
        hm: PromptHistoryManager = self._history_manager
        return hm

    @property
    def is_mounted(self) -> bool:
        """Check if application is running and mounted.

        Parameters
        ------------
        None

        Returns
        --------
            bool: boolean object
                True if application is mounted and running.
        """
        return bool(self._is_mounted)

    def compose(self) -> ComposeResult:
        """Compose layout widgets for the interactive chat interface.

        Parameters
        ------------
        None

        Returns
        --------
            ComposeResult: ComposeResult generator
                Yields header, banner, scroll area, input, and telemetry bar.
        """
        yield Header()
        is_init: bool = (self._workspace_dir / ".neuri").is_dir()
        init_badge: str = "[Initialized]" if is_init else "[Type /init to setup]"
        banner_text: str = (
            f" Workspace: {self._workspace_dir.name} ({self._workspace_dir})  │  "
            f"State: {init_badge}"
        )
        yield Static(banner_text, id="workspace-banner")

        with Horizontal(id="main-horizontal"):
            yield VerticalScroll(id="chat-scroll")
            yield self._compute_sidebar

        with Container(id="input-container"):
            yield self._machine_selector_bar
            yield PromptInput(
                placeholder=(
                    "Type a research prompt or /command (/init, /skills, "
                    "/machines, /status, /help, /exit)..."
                ),
                id="prompt-input",
                select_on_focus=False,
            )

        yield self._telemetry_bar
        yield Footer()

    async def on_mount(self) -> None:
        """Triggered when application interface finishes mounting.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Focuses input widget, posts welcome card, and starts monitors.
        """
        input_widget: PromptInput = self.query_one(
            "#prompt-input", PromptInput
        )
        input_widget.focus()

        # Register all available themes and activate configured theme
        for thm in self._theme_manager.list_available_themes():
            self.register_theme(thm.to_textual_theme())
        active_theme_name: str = self._theme_manager.get_active_theme_name()
        self.apply_theme(active_theme_name)

        # Mount initial welcome card
        welcome_turn: ChatTurn = ChatTurn(
            turn_id="welcome_turn",
            role=ChatRole.ASSISTANT,
            content=(
                "- Type `/help` for all slash commands.\n"
            ),
        )
        scroll_area: VerticalScroll = self.query_one(
            "#chat-scroll", VerticalScroll
        )
        await scroll_area.mount(MessageCard(welcome_turn))

        # Initial machine query and periodic monitor loop
        self.set_interval(15.0, self.refresh_compute_machines)
        asyncio.create_task(self.refresh_compute_machines())

    @property
    def active_neuri_theme(self) -> NeuriTheme:
        """Get the active NeuriTheme instance.

        Parameters
        ------------
        None

        Returns
        --------
            NeuriTheme: NeuriTheme instance
                Currently active theme object.
        """
        active_theme_str: str = getattr(self, "theme", "")
        if active_theme_str:
            thm: NeuriTheme | None = self._theme_manager.get_theme(
                active_theme_str
            )
            if thm is not None:
                return thm
        return self._theme_manager.get_high_contrast_theme()

    def apply_theme(self, theme_name: str) -> None:
        """Apply a color theme by name to the Textual user interface.

        Parameters
        ------------
        theme_name: str
            Theme name or alias (e.g. 'high_contrast', 'dark', 'monokai', 'nord').

        Returns
        --------
            None: NoneType object
                Updates active application theme and re-styles widgets.
        """
        clean_name: str = theme_name.strip().lower()
        if clean_name not in self.available_themes:
            thm: NeuriTheme | None = self._theme_manager.get_theme(clean_name)
            if thm is not None:
                self.register_theme(thm.to_textual_theme())
        if clean_name in self.available_themes:
            self.theme = clean_name

        active_thm: NeuriTheme = self.active_neuri_theme
        if (
            hasattr(self, "_compute_sidebar")
            and self._compute_sidebar is not None
        ):
            self._compute_sidebar.refresh_theme(active_thm)
        if (
            hasattr(self, "_machine_selector_bar")
            and self._machine_selector_bar is not None
        ):
            self._machine_selector_bar.refresh_theme(active_thm)
        if hasattr(self, "_telemetry_bar") and self._telemetry_bar is not None:
            self._telemetry_bar.refresh_theme(active_thm)

    def action_toggle_sidebar(self) -> None:
        """Toggle visibility of the compute machines and jobs sidebar.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Toggles the hidden CSS class on the sidebar widget.
        """
        self._compute_sidebar.toggle_class("hidden")

    @property
    def is_shell_mode(self) -> bool:
        """Check if application is currently in shell execution mode.

        Parameters
        ------------
        None

        Returns
        --------
            bool: boolean object
                True if shell mode is active.
        """
        return self._is_shell_mode

    @property
    def selected_machine(self) -> str:
        """Return the currently selected machine alias.

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                Active machine alias.
        """
        if (
            self._available_machines
            and 0 <= self._selected_machine_index < len(self._available_machines)
        ):
            return self._available_machines[self._selected_machine_index]
        return "localhost"

    def action_toggle_shell_mode(self) -> None:
        """Toggle between natural language prompt mode and shell mode.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Toggles shell mode state and updates input UI styling.
        """
        self._is_shell_mode = not self._is_shell_mode
        if self._is_shell_mode:
            self._available_machines = self._shell_executor.get_available_hosts(
                config=self._engine.config
            )
            self._selected_machine_index = 0
        self._update_shell_mode_ui()

    def action_next_machine(self) -> None:
        """Select the next available machine in shell mode.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Cycles selected machine index forward.
        """
        if not self._is_shell_mode or not self._available_machines:
            return
        self._selected_machine_index = (
            self._selected_machine_index + 1
        ) % len(self._available_machines)
        self._update_shell_mode_ui()

    def action_prev_machine(self) -> None:
        """Select the previous available machine in shell mode.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Cycles selected machine index backward.
        """
        if not self._is_shell_mode or not self._available_machines:
            return
        self._selected_machine_index = (
            self._selected_machine_index - 1
        ) % len(self._available_machines)
        self._update_shell_mode_ui()

    def _update_shell_mode_ui(self) -> None:
        """Update input widget styling and machine selector bar visibility.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Synchronizes UI components with shell mode state.
        """
        input_widget: PromptInput = self.query_one(
            "#prompt-input", PromptInput
        )
        selector_bar: MachineSelectorBar = self._machine_selector_bar

        if self._is_shell_mode:
            if not self._available_machines:
                self._available_machines = ["localhost"]
            self._selected_machine_index = min(
                self._selected_machine_index,
                max(0, len(self._available_machines) - 1),
            )
            active_host: str = self.selected_machine

            selector_bar.remove_class("hidden")
            selector_bar.update_selection(
                machines=self._available_machines,
                current_index=self._selected_machine_index,
            )

            input_widget.add_class("shell-mode")
            input_widget.placeholder = (
                f"Enter shell command for [{active_host}] "
                "($ ls -la, nvidia-smi, git status)..."
            )
            self._telemetry_bar.status_text = f"Shell [{active_host}]"
            if not self._shell_executor.is_local(active_host):
                asyncio.create_task(
                    self._shell_executor.warm_host(active_host)
                )
        else:
            selector_bar.add_class("hidden")
            input_widget.remove_class("shell-mode")
            input_widget.placeholder = (
                "Type a research prompt or /command (/init, /skills, "
                "/machines, /status, /help, /exit)..."
            )
            self._telemetry_bar.status_text = "Ready"

    async def refresh_compute_machines(self) -> None:
        """Query attached machines and update the compute sidebar widget.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Updates sidebar content asynchronously.
        """
        try:
            from neuri.remote.monitor import RemoteHostMonitor

            monitor: RemoteHostMonitor = RemoteHostMonitor()
            hosts: list[str] = monitor.get_configured_hosts()
            default_host: str = getattr(
                getattr(self._engine.config, "project", None),
                "default_remote_host",
                "localhost",
            )
            if default_host not in hosts:
                hosts.insert(0, default_host)

            data: list[dict[str, Any]] = await monitor.query_all_hosts(hosts)
            self._compute_sidebar.update_machines(data)

            online_count: int = sum(1 for d in data if d.get("online"))
            active_jobs: int = sum(
                len(d.get("neuri_jobs", [])) + len(d.get("slurm_jobs", []))
                for d in data
            )
            self._telemetry_bar.machines_summary = (
                f"{online_count}/{len(data)} online"
            )
            if active_jobs > 0:
                self._telemetry_bar.status_text = f"{active_jobs} Jobs Active"
        except Exception:
            pass

    async def on_key(self, event: events.Key) -> None:
        """Capture key events and redirect typing to prompt input automatically.

        Parameters
        ------------
        event: events.Key
            Key event captured at application root.

        Returns
        --------
            None: NoneType object
                Focuses prompt input and enters characters if unfocused.
        """
        try:
            input_widget: PromptInput = self.query_one(
                "#prompt-input", PromptInput
            )
        except Exception:
            return

        if self.focused != input_widget:
            if event.is_printable and event.character:
                input_widget.focus()
                input_widget.insert_text_at_cursor(event.character)
                event.prevent_default()
                event.stop()
            elif event.key == "backspace":
                input_widget.focus()
                input_widget.action_delete_left()
                event.prevent_default()
                event.stop()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle prompt submission from the bottom input box.

        Parameters
        ------------
        event: Input.Submitted
            Input submission event containing user text.

        Returns
        --------
            None: NoneType object
                Asynchronously dispatches input to session engine.
        """
        val: str = event.value.strip()
        if not val:
            return

        self._history_manager.add_entry(val)

        input_widget: Input = event.input
        input_widget.value = ""
        input_widget.disabled = True
        self._telemetry_bar.status_text = "Processing..."

        # Mount user message card
        scroll_area: VerticalScroll = self.query_one(
            "#chat-scroll", VerticalScroll
        )

        if self._is_shell_mode:
            target_host: str = self.selected_machine
            self._telemetry_bar.status_text = f"Running on {target_host}..."

            user_sh_turn: ChatTurn = ChatTurn(
                turn_id=f"u_sh_{int(datetime.now(timezone.utc).timestamp())}",
                role=ChatRole.USER,
                content=f"**[{target_host}]** `$ {val}`",
            )
            await scroll_area.mount(MessageCard(user_sh_turn))
            scroll_area.scroll_end(animate=False)

            try:
                res: ShellExecutionResult = await self._shell_executor.execute(
                    command=val, host=target_host
                )
                card_md: str = self._shell_executor.format_markdown_card(res)
                assistant_sh_turn: ChatTurn = ChatTurn(
                    turn_id=f"a_sh_{int(datetime.now(timezone.utc).timestamp())}",
                    role=ChatRole.ASSISTANT,
                    content=card_md,
                )
                await scroll_area.mount(MessageCard(assistant_sh_turn))
                scroll_area.scroll_end(animate=False)
            except Exception as exc:
                err_sh_turn: ChatTurn = ChatTurn(
                    turn_id=f"err_{int(datetime.now(timezone.utc).timestamp())}",
                    role=ChatRole.ASSISTANT,
                    content=f"**Shell Execution Error:** `{exc}`",
                )
                await scroll_area.mount(MessageCard(err_sh_turn))
                scroll_area.scroll_end(animate=False)
            finally:
                input_widget.disabled = False
                input_widget.focus()
                self._telemetry_bar.status_text = f"Shell [{target_host}]"
            return

        user_turn: ChatTurn = ChatTurn(
            turn_id=f"u_{int(datetime.now(timezone.utc).timestamp())}",
            role=ChatRole.USER,
            content=val,
        )
        await scroll_area.mount(MessageCard(user_turn))
        scroll_area.scroll_end(animate=False)

        try:
            assistant_turn: ChatTurn = await self._engine.submit_user_input(val)
            await scroll_area.mount(MessageCard(assistant_turn))
            scroll_area.scroll_end(animate=False)
        except Exception as exc:
            err_turn: ChatTurn = ChatTurn(
                turn_id=f"err_{int(datetime.now(timezone.utc).timestamp())}",
                role=ChatRole.ASSISTANT,
                content=f"**Error executing turn:** `{exc}`",
            )
            await scroll_area.mount(MessageCard(err_turn))
            scroll_area.scroll_end(animate=False)
        finally:
            input_widget.disabled = False
            input_widget.focus()
            self._telemetry_bar.status_text = "Ready"

    def _handle_session_event(self, ev: SessionEvent) -> None:
        """Handle incoming SessionEvent from session engine.

        Parameters
        ------------
        ev: SessionEvent
            Dispatched session event.

        Returns
        --------
            None: NoneType object
                Updates telemetry footer and triggers UI actions.
        """
        if ev.event_type == SessionEventType.STATUS_UPDATE:
            action: Any = ev.payload.get("action")
            if action == "clear_chat":
                self.action_clear_screen()
            elif action == "exit_app":
                self.exit()
            elif action == "change_theme":
                data_dict: dict[str, Any] = ev.payload.get("data") or {}
                thm_name: str = str(
                    data_dict.get("theme_name")
                    or ev.payload.get("theme_name", "high_contrast")
                )
                self.apply_theme(thm_name)
            elif action == "reload_config":
                banner: Static = self.query_one("#workspace-banner", Static)
                banner.update(
                    f" Workspace: {self._workspace_dir.name} "
                    f"({self._workspace_dir})  │  State: [Initialized]"
                )
            elif action == "token_increment":
                toks_inc: int = int(ev.payload.get("tokens", 0))
                cost_inc: float = float(ev.payload.get("cost_usd", 0.0))
                self._telemetry_bar.tokens_count += toks_inc
                self._telemetry_bar.cost_usd += cost_inc

        elif ev.event_type == SessionEventType.THINKING_CHUNK:
            self._telemetry_bar.status_text = "Reasoning..."

        elif ev.event_type == SessionEventType.CIRCUIT_BREAKER_TRIGGERED:
            self._telemetry_bar.status_text = "Circuit Breaker Tripped"

        elif ev.event_type == SessionEventType.WORKFLOW_COMPLETED:
            toks: int = int(ev.payload.get("total_tokens", 0))
            cost: float = float(ev.payload.get("cost_usd", 0.0))
            self._telemetry_bar.tokens_count += toks
            self._telemetry_bar.cost_usd += cost
            self._telemetry_bar.status_text = "Ready"

    def action_clear_screen(self) -> None:
        """Clear all messages from the chat scroll area.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Removes message card children.
        """
        scroll_area: VerticalScroll = self.query_one(
            "#chat-scroll", VerticalScroll
        )
        scroll_area.remove_children()
        self._engine.clear_turns()


__all__: list[str] = [
    "ComputeSidebar",
    "MachineSelectorBar",
    "MessageCard",
    "NeuriChatApp",
    "PromptInput",
    "TelemetryBar",
]
