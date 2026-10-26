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
                f"❯ You  ({self._turn.timestamp.strftime('%H:%M:%S')})",
                classes="user-header",
            )
            yield Static(self._turn.content, classes="user-body")
        else:
            yield Label(
                f"◆ Neuri  ({self._turn.timestamp.strftime('%H:%M:%S')})",
                classes="assistant-header",
            )
            if self._turn.thinking_trace:
                with Collapsible(title="🧠 Reasoning Trace", collapsed=True):
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
        yield Label(" 💻 Machines & Jobs [F2] ", id="compute-sidebar-title")
        yield self._content

    def update_machines(self, machines_data: list[dict[str, Any]]) -> None:
        """Render formatted machine status and active jobs into sidebar.

        Parameters
        ------------
        machines_data: list[dict[str, Any]]
            List of machine health and job dictionaries.

        Returns
        --------
            None: NoneType object
                Updates text inside sidebar content widget.
        """
        if not machines_data:
            self._content.update(
                "[dim]No attached machines.\nUse /remote bootstrap <host>[/dim]"
            )
            return

        txt: Text = Text()
        for idx, m in enumerate(machines_data):
            if idx > 0:
                txt.append("\n" + "─" * 26 + "\n")
            host_name: str = str(m.get("host", "unknown"))
            online: bool = bool(m.get("online", False))
            if online:
                txt.append("● ", style="bold green")
                txt.append(f"{host_name}\n", style="bold white")
                cores: int = int(m.get("cpu_count", 1))
                load_arr: list[float] = m.get("load_avg", [0.0, 0.0, 0.0])
                load_s: str = f"{load_arr[0]:.2f}" if load_arr else "-"
                txt.append(f"  CPUs: {cores} │ Load: {load_s}\n", style="cyan")

                n_jobs: list[dict[str, Any]] = m.get("neuri_jobs", [])
                s_jobs: list[dict[str, Any]] = m.get("slurm_jobs", [])
                total_jobs: int = len(n_jobs) + len(s_jobs)
                if total_jobs == 0:
                    txt.append("  Jobs: Idle\n", style="dim")
                else:
                    for nj in n_jobs:
                        st: str = str(nj.get("state", "RUNNING"))
                        style_tag: str = (
                            "green" if st == "RUNNING" else "yellow"
                        )
                        txt.append(
                            f"  ▶ [Neuri] {nj.get('job_id')}: {st}\n",
                            style=style_tag,
                        )
                    for sj in s_jobs:
                        st = str(sj.get("state", "R"))
                        style_tag = (
                            "green" if st in ("R", "RUNNING") else "yellow"
                        )
                        txt.append(
                            f"  ▶ [Slurm] #{sj.get('slurm_job_id')}: {st}\n",
                            style=style_tag,
                        )
            else:
                txt.append("○ ", style="bold red")
                txt.append(f"{host_name} (Offline)\n", style="dim red")

        self._content.update(txt)


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

    def __init__(self, harness_id: str = "agy") -> None:
        """Initialize telemetry status bar.

        Parameters
        ------------
        harness_id: str
            Harness identifier string. Defaults to 'agy'.

        Returns
        --------
            None: NoneType object
                Initializes widget attributes.
        """
        super().__init__()
        self._harness_id: str = harness_id

    def render(self) -> Text:
        """Render formatted rich text for telemetry footer.

        Parameters
        ------------
        None

        Returns
        --------
            Text: Text object
                Rich text display.
        """
        txt: Text = Text()
        txt.append(" Harness: ", style="bold cyan")
        txt.append(f"{self._harness_id} ", style="green")
        txt.append("│ Machines: ", style="bold cyan")
        txt.append(f"{self.machines_summary} ", style="green")
        txt.append("│ Tokens: ", style="bold cyan")
        txt.append(f"{self.tokens_count:,} ", style="yellow")
        txt.append("│ Cost: ", style="bold cyan")
        txt.append(f"${self.cost_usd:.4f} ", style="magenta")
        txt.append("│ Status: ", style="bold cyan")
        txt.append(f"{self.status_text}", style="bold green")
        return txt


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
    SUB_TITLE = "Vendor-Agnostic Neuroscience Meta-Harness (v0.1.0)"

    CSS = """
    Screen {
        background: #12141a;
        color: #e2e8f0;
    }
    #workspace-banner {
        dock: top;
        height: 2;
        background: #1e2430;
        color: #94a3b8;
        padding: 0 1;
        border-bottom: solid #334155;
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
        background: #161a22;
        border-left: solid #334155;
        padding: 0 1;
    }
    #compute-sidebar.hidden {
        display: none;
    }
    #compute-sidebar-title {
        color: #38bdf8;
        text-style: bold;
        background: #1e2430;
        padding: 0 1;
        margin-bottom: 1;
        width: 100%;
    }
    #compute-sidebar-content {
        color: #cbd5e1;
    }
    #input-container {
        dock: bottom;
        height: auto;
        padding: 0 1 1 1;
        background: #12141a;
    }
    Input {
        border: tall #3b82f6;
        background: #1e2430;
        color: #f8fafc;
    }
    Input:focus {
        border: tall #60a5fa;
    }
    #telemetry-bar {
        dock: bottom;
        height: 1;
        background: #0f172a;
        color: #64748b;
        padding: 0 1;
    }
    .user-header {
        color: #38bdf8;
        text-style: bold;
        margin-top: 1;
    }
    .user-body {
        margin-left: 2;
        margin-bottom: 1;
        color: #f1f5f9;
    }
    .assistant-header {
        color: #a78bfa;
        text-style: bold;
        margin-top: 1;
    }
    .assistant-body {
        margin-left: 2;
        margin-bottom: 1;
    }
    .thinking-text {
        color: #94a3b8;
        text-style: italic;
        padding: 1;
        background: #1a202c;
    }
    """

    BINDINGS: list[Binding] = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+q", "quit", "Quit", show=False),
        Binding("ctrl+l", "clear_screen", "Clear", show=True),
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
        self._engine.subscribe(self._handle_session_event)

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
            yield Input(
                placeholder=(
                    "Type a research prompt or /command (/init, /skills, "
                    "/machines, /status, /help, /exit)..."
                ),
                id="prompt-input",
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
        input_widget: Input = self.query_one("#prompt-input", Input)
        input_widget.focus()

        # Mount initial welcome card
        welcome_turn: ChatTurn = ChatTurn(
            turn_id="welcome_turn",
            role=ChatRole.ASSISTANT,
            content=(
                "**Welcome to Neuri v0.1.0** — Vendor-Agnostic Neuroscience "
                "Meta-Harness.\n\n"
                "- Press `F2` to toggle the attached Machines & Compute sidebar.\n"
                "- Type `/machines` to view cluster and remote compute node status.\n"
                "- Type `/skills` to explore available neuroscience skill packs.\n"
                "- Type `/init` to initialize project configuration and SQLite state.\n"
                "- Type `/status` to view active harness and token budgets.\n"
                "- Type `/help` for all slash commands.\n"
                "- Or enter any natural language neuroscience research instruction."
            ),
        )
        scroll_area: VerticalScroll = self.query_one(
            "#chat-scroll", VerticalScroll
        )
        await scroll_area.mount(MessageCard(welcome_turn))

        # Initial machine query and periodic monitor loop
        self.set_interval(15.0, self.refresh_compute_machines)
        asyncio.create_task(self.refresh_compute_machines())

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

        input_widget: Input = event.input
        input_widget.value = ""
        input_widget.disabled = True
        self._telemetry_bar.status_text = "Processing..."

        # Mount user message card
        scroll_area: VerticalScroll = self.query_one(
            "#chat-scroll", VerticalScroll
        )
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
    "MessageCard",
    "NeuriChatApp",
    "TelemetryBar",
]
