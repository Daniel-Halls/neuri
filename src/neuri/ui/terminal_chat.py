"""Interactive Terminal Chat Interface for Neuri (Textual TUI).

Implements the agy-style interactive terminal chat window launched via `neuri`.
Provides a rich scrollable canvas, slash-command autocompletion, collapsible
reasoning drawers, and live telemetry status bars.
"""

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
    #chat-scroll {
        height: 1fr;
        padding: 1 2;
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

        yield VerticalScroll(id="chat-scroll")

        with Container(id="input-container"):
            yield Input(
                placeholder=(
                    "Type a research prompt or /command (/init, /skills, "
                    "/status, /help, /exit)..."
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
                Focuses the prompt input widget and posts welcome card.
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
    "MessageCard",
    "NeuriChatApp",
    "TelemetryBar",
]
