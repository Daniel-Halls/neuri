"""Interactive Terminal Chat Interface for Neuri (Textual TUI).

Implements the agy-style interactive terminal chat window launched via `neuri`.
Provides a rich scrollable canvas, slash-command autocompletion, collapsible
reasoning drawers, and live telemetry status bars.

Styling rule: this module never contains colour literals. Every colour is a
semantic theme token (``$primary``, ``$muted``, ``$border`` ...) resolved by
Textual from the active Neuri theme, either in the CSS below or inside
``Content`` styles. Switching themes therefore restyles every widget live.
"""

import asyncio
import contextlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.content import Content
from textual.reactive import reactive
from textual.widgets import (
    Collapsible,
    Footer,
    Input,
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


class Glyphs:
    """Shared text glyphs used across the TUI (no emoji, no pictures).

    Parameters
    ------------
    None

    Returns
    --------
        Glyphs: Glyphs class
            Namespace of plain Unicode text glyphs.
    """

    BRAND: ClassVar[str] = ">>"
    DOT_ON: ClassVar[str] = "●"
    DOT_OFF: ClassVar[str] = "○"
    PROMPT: ClassVar[str] = "›"
    SEP: ClassVar[str] = "│"
    BAR_FULL: ClassVar[str] = "█"
    BAR_EMPTY: ClassVar[str] = "░"
    RULE: ClassVar[str] = "─"


def render_meter(
    val: float, max_val: float, width: int, fill_style: str
) -> Content:
    """Render a themed Unicode capacity meter such as '████░░░░'.

    Parameters
    ------------
    val: float
        Current numeric value.
    max_val: float
        Maximum capacity value.
    width: int
        Cell width of the bar.
    fill_style: str
        Theme style token applied to the filled cells (e.g. '$primary').

    Returns
    --------
        Content: Content object
            Meter with filled cells in ``fill_style`` and empty cells in
            ``$border``.
    """
    ratio: float = min(1.0, max(0.0, val / max_val)) if max_val > 0.0 else 0.0
    filled: int = int(round(ratio * width))
    meter: Content = Content.assemble(
        (Glyphs.BAR_FULL * filled, fill_style),
        (Glyphs.BAR_EMPTY * (width - filled), "$border"),
    )
    return meter


def card_header(glyph: str, label: str, style: str, stamp: str) -> Content:
    """Build the one-line header shown at the top of each chat card.

    Parameters
    ------------
    glyph: str
        Leading glyph (e.g. '›').
    label: str
        Role label text.
    style: str
        Theme style token for glyph and label.
    stamp: str
        Timestamp string rendered in ``$muted``.

    Returns
    --------
        Content: Content object
            Styled header line.
    """
    header: Content = Content.assemble(
        (f"{glyph} ", f"bold {style}"),
        (label, f"bold {style}"),
        ("  ", ""),
        (stamp, "$muted"),
    )
    return header


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
        """Initialize message card with role-specific styling classes.

        Parameters
        ------------
        turn: ChatTurn
            The chat turn data model.

        Returns
        --------
            None: NoneType object
                Initializes widget state.
        """
        self._turn: ChatTurn = turn
        self._kind: str = self._classify(turn)
        super().__init__(classes=f"message-card message-card-{self._kind}")

    @staticmethod
    def _classify(turn: ChatTurn) -> str:
        """Classify a turn as 'user', 'assistant', or 'shell'.

        Parameters
        ------------
        turn: ChatTurn
            Chat turn to classify.

        Returns
        --------
            str: string object
                Card kind used for CSS class selection.
        """
        if turn.role == ChatRole.USER:
            is_shell: bool = "**[" in turn.content and "$ " in turn.content
            kind: str = "shell" if is_shell else "user"
        else:
            is_shell_out: bool = "### Shell Output:" in turn.content
            kind = "shell" if is_shell_out else "assistant"
        return kind

    def compose(self) -> ComposeResult:
        """Compose child widgets inside the message card.

        Parameters
        ------------
        None

        Returns
        --------
            ComposeResult: ComposeResult generator
                Yields header label and body widgets.
        """
        time_str: str = self._turn.timestamp.strftime("%H:%M:%S")
        if self._kind == "user":
            yield Static(
                card_header(Glyphs.PROMPT, "you", "$primary", time_str),
                classes="card-header",
            )
            yield Static(Content(self._turn.content), classes="card-body")
        elif self._kind == "shell":
            yield Static(
                card_header(Glyphs.PROMPT, "shell", "$success", time_str),
                classes="card-header",
            )
            yield Markdown(self._turn.content, classes="card-body")
        else:
            role_label: str = (
                f"specialist · {self._turn.node_id}"
                if self._turn.node_id
                else "neuri"
            )
            yield Static(
                card_header(Glyphs.BRAND, role_label, "$secondary", time_str),
                classes="card-header",
            )
            if self._turn.thinking_trace:
                with Collapsible(title="reasoning trace", collapsed=True):
                    yield Static(
                        Content(self._turn.thinking_trace),
                        classes="thinking-text",
                    )
            yield Markdown(self._turn.content, classes="card-body")


class ShellCommandCard(Static):
    """Prompt-style line echoing a shell command and its target host.

    Parameters
    ------------
    host: str
        Machine alias the command runs on.
    command: str
        Shell command text.

    Returns
    --------
        ShellCommandCard: ShellCommandCard instance
            Constructed command echo widget.
    """

    def __init__(self, host: str, command: str) -> None:
        """Initialize the command echo line.

        Parameters
        ------------
        host: str
            Machine alias the command runs on.
        command: str
            Shell command text.

        Returns
        --------
            None: NoneType object
                Initializes widget state.
        """
        line: Content = Content.assemble(
            (host, "bold $secondary"),
            (" on ", "$muted"),
            ("shell", "bold $accent"),
            ("\n", ""),
            (f"{Glyphs.PROMPT} ", "bold $primary"),
            (command, "$foreground"),
        )
        super().__init__(line, classes="shell-command")


class ShellResultCard(Static):
    """Terminal-style block rendering stdout, stderr, and exit status.

    Parameters
    ------------
    result: ShellExecutionResult
        Completed shell execution result.

    Returns
    --------
        ShellResultCard: ShellResultCard instance
            Constructed shell output widget.
    """

    def __init__(self, result: ShellExecutionResult) -> None:
        """Initialize the output block with exit-status styling.

        Parameters
        ------------
        result: ShellExecutionResult
            Completed shell execution result.

        Returns
        --------
            None: NoneType object
                Initializes widget state.
        """
        status: str = "ok" if result.exit_code == 0 else "failed"
        super().__init__(classes=f"shell-result shell-result-{status}")
        self._result: ShellExecutionResult = result

    def compose(self) -> ComposeResult:
        """Compose stdout, stderr, and status footer lines.

        Parameters
        ------------
        None

        Returns
        --------
            ComposeResult: ComposeResult generator
                Yields output and footer widgets.
        """
        res: ShellExecutionResult = self._result
        if res.stdout.strip():
            yield Static(Content(res.stdout.rstrip()), classes="shell-stdout")
        if res.stderr.strip():
            yield Static(
                Content.assemble((res.stderr.rstrip(), "$error")),
                classes="shell-stderr",
            )
        ok: bool = res.exit_code == 0
        status_style: str = "$success" if ok else "$error"
        yield Static(
            Content.assemble(
                (f"{Glyphs.DOT_ON} ", status_style),
                (f"exit {res.exit_code}", f"bold {status_style}"),
                (f"  {Glyphs.SEP}  ", "$border"),
                (f"{res.duration_seconds:.2f}s", "$muted"),
                (f"  {Glyphs.SEP}  ", "$border"),
                (res.host, "$muted"),
            ),
            classes="shell-footer",
        )


class WelcomeCard(Static):
    """Landing panel with workspace status and a quick-action table.

    Parameters
    ------------
    workspace_dir: Path
        Active workspace directory.

    Returns
    --------
        WelcomeCard: WelcomeCard instance
            Constructed welcome widget.
    """

    COLUMNS: ClassVar[tuple[str, str, str]] = (
        "Modality",
        "Quick Action",
        "Command",
    )
    ROWS: ClassVar[list[tuple[str, str, list[tuple[str, str]]]]] = [
        (
            "Natural Language",
            "Decompose & execute research DAG",
            [("Enter any instruction", "")],
        ),
        (
            "DAG Preview",
            "Preview execution plan without running",
            [("/plan <instruction>", "$primary")],
        ),
        (
            "3D Visualization",
            "Inspect NIfTI / GIfTI in WebGL2 bridge",
            [("/view [path]", "$primary")],
        ),
        (
            "Status & Jobs",
            "Inspect nodes, artifacts, and batch queues",
            [("/status", "$primary"), (" or ", ""), ("/jobs", "$primary")],
        ),
        (
            "Fleet Shell",
            "Run bash command locally or on cluster",
            [("!<cmd>", "$primary"), (" or ", ""), ("Ctrl+S", "$primary")],
        ),
        (
            "Command Help",
            "List all interactive slash commands",
            [("/help", "$primary")],
        ),
    ]

    def __init__(self, workspace_dir: Path) -> None:
        """Initialize welcome card for a workspace.

        Parameters
        ------------
        workspace_dir: Path
            Active workspace directory.

        Returns
        --------
            None: NoneType object
                Initializes widget state.
        """
        super().__init__(classes="welcome-card")
        self._workspace_dir: Path = workspace_dir

    def _status_line(self) -> Content:
        """Build the workspace / state / theme status line.

        Parameters
        ------------
        None

        Returns
        --------
            Content: Content object
                Styled status line.
        """
        is_init: bool = (self._workspace_dir / ".neuri").is_dir()
        state_part: tuple[str, str] = (
            (" Initialized ", "bold $selection-fg on $selection-bg")
            if is_init
            else (" Uninitialized - run /init ", "bold $background on $warning")
        )
        theme_name: str = str(getattr(self.app, "theme", "") or "default")
        sep: tuple[str, str] = (f" {Glyphs.SEP} ", "$border")
        line: Content = Content.assemble(
            (f"{Glyphs.DOT_ON} ", "$secondary"),
            ("Workspace: ", "bold $foreground"),
            (str(self._workspace_dir), "$primary"),
            sep,
            ("State: ", "bold $foreground"),
            state_part,
            sep,
            ("Theme: ", "bold $foreground"),
            (theme_name, "$accent"),
        )
        return line

    def _column_widths(self) -> list[int]:
        """Compute padded column widths for the quick-action table.

        Parameters
        ------------
        None

        Returns
        --------
            list[int]: list object
                Cell widths including one space of padding on each side.
        """
        widths: list[int] = [len(col) for col in self.COLUMNS]
        for modality, action, command in self.ROWS:
            cmd_len: int = sum(len(text) for text, _ in command)
            widths[0] = max(widths[0], len(modality))
            widths[1] = max(widths[1], len(action))
            widths[2] = max(widths[2], cmd_len)
        padded: list[int] = [w + 2 for w in widths]
        return padded

    @staticmethod
    def _rule(widths: list[int], left: str, mid: str, right: str) -> Content:
        """Build a horizontal table rule such as '├────┼────┤'.

        Parameters
        ------------
        widths: list[int]
            Padded column widths.
        left: str
            Left corner / junction glyph.
        mid: str
            Inner junction glyph.
        right: str
            Right corner / junction glyph.

        Returns
        --------
            Content: Content object
                Rule line styled with ``$border``.
        """
        body: str = mid.join(Glyphs.RULE * w for w in widths)
        rule: Content = Content.assemble((f"{left}{body}{right}\n", "$border"))
        return rule

    @staticmethod
    def _row(widths: list[int], cells: list[list[tuple[str, str]]]) -> Content:
        """Build one bordered table row from styled cell fragments.

        Parameters
        ------------
        widths: list[int]
            Padded column widths.
        cells: list[list[tuple[str, str]]]
            Per-column list of (text, style) fragments.

        Returns
        --------
            Content: Content object
                Row line with ``$border`` separators.
        """
        parts: list[str | Content | tuple[str, str]] = [(Glyphs.SEP, "$border")]
        for width, fragments in zip(widths, cells, strict=True):
            used: int = sum(len(text) for text, _ in fragments)
            parts.append(" ")
            parts.extend(fragments)
            parts.append(" " * (width - used - 1))
            parts.append((Glyphs.SEP, "$border"))
        parts.append("\n")
        row: Content = Content.assemble(*parts)
        return row

    def _table(self) -> Content:
        """Build the full quick-action table.

        Parameters
        ------------
        None

        Returns
        --------
            Content: Content object
                Box-drawn table using theme tokens only.
        """
        widths: list[int] = self._column_widths()
        header_cells: list[list[tuple[str, str]]] = [
            [(col, "bold $secondary")] for col in self.COLUMNS
        ]
        parts: list[str | Content | tuple[str, str]] = [
            self._rule(widths, "┌", "┬", "┐"),
            self._row(widths, header_cells),
        ]
        for modality, action, command in self.ROWS:
            parts.append(self._rule(widths, "├", "┼", "┤"))
            parts.append(
                self._row(
                    widths,
                    [[(modality, "$foreground")], [(action, "$foreground")],
                     command],
                )
            )
        parts.append(self._rule(widths, "└", "┴", "┘"))
        table: Content = Content.assemble(*parts)
        return table

    def render(self) -> Content:
        """Render title, status line, and quick-action table.

        Parameters
        ------------
        None

        Returns
        --------
            Content: Content object
                Complete welcome panel content.
        """
        welcome: Content = Content.assemble(
            (f"{Glyphs.BRAND} NEURI", "bold $primary"),
            (" - Neuroscience Meta-Harness\n\n", "bold $primary"),
            self._status_line(),
            "\n\n",
            self._table(),
        )
        return welcome.rstrip()


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

    RULE_WIDTH: ClassVar[int] = 28
    METER_WIDTH: ClassVar[int] = 8

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
        self.border_title = "Machines"
        self.border_subtitle = "F2"
        self._content: Static = Static(
            Content.assemble(("Loading compute fabric...", "$muted")),
            id="compute-sidebar-content",
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
                Yields content widget.
        """
        yield self._content

    @staticmethod
    def _load_style(load_val: float, cores: int) -> str:
        """Choose a semantic style for a host's load relative to its cores.

        Parameters
        ------------
        load_val: float
            One-minute load average.
        cores: int
            Number of CPU cores.

        Returns
        --------
            str: string object
                '$primary' when healthy, '$warning' when busy, '$error' when
                oversubscribed.
        """
        ratio: float = load_val / max(1, cores)
        style: str = "$primary"
        if ratio >= 1.0:
            style = "$error"
        elif ratio >= 0.75:
            style = "$warning"
        return style

    def _machine_block(
        self, machine: dict[str, Any]
    ) -> list[str | Content | tuple[str, str]]:
        """Build the styled lines describing one machine.

        Parameters
        ------------
        machine: dict[str, Any]
            Machine health and job dictionary.

        Returns
        --------
            list[str | Content | tuple[str, str]]: list object
                Content fragments for this machine.
        """
        host_name: str = str(machine.get("host", "unknown"))
        if not bool(machine.get("online", False)):
            offline: list[str | Content | tuple[str, str]] = [
                (f"{Glyphs.DOT_OFF} ", "bold $error"),
                (f"{host_name}\n", "bold $foreground"),
                ("  offline\n", "$error"),
            ]
            return offline

        cores: int = int(machine.get("cpu_count", 1))
        load_arr: list[float] = machine.get("load_avg", [0.0, 0.0, 0.0])
        load_val: float = float(load_arr[0]) if load_arr else 0.0
        load_s: str = f"{load_val:.2f}" if load_arr else "-"
        load_style: str = self._load_style(load_val, cores)
        parts: list[str | Content | tuple[str, str]] = [
            (f"{Glyphs.DOT_ON} ", "bold $success"),
            (f"{host_name}\n", "bold $foreground"),
            ("  Load  ", "$muted"),
            render_meter(
                load_val, max(1.0, float(cores)), self.METER_WIDTH, load_style
            ),
            (f" {load_s}\n", load_style),
            ("  CPUs  ", "$muted"),
            (f"{cores} cores\n", "$foreground"),
        ]

        n_jobs: list[dict[str, Any]] = machine.get("neuri_jobs", [])
        s_jobs: list[dict[str, Any]] = machine.get("slurm_jobs", [])
        if not n_jobs and not s_jobs:
            parts.extend([("  Jobs  ", "$muted"), ("idle\n", "$foreground")])
        for nj in n_jobs:
            st: str = str(nj.get("state", "RUNNING"))
            job_style: str = "$success" if st == "RUNNING" else "$warning"
            parts.extend([
                ("  neuri ", "$muted"),
                (f"{nj.get('job_id')} ", "$foreground"),
                (f"{st}\n", job_style),
            ])
        for sj in s_jobs:
            st = str(sj.get("state", "R"))
            job_style = "$success" if st in ("R", "RUNNING") else "$warning"
            parts.extend([
                ("  slurm ", "$muted"),
                (f"#{sj.get('slurm_job_id')} ", "$foreground"),
                (f"{st}\n", job_style),
            ])
        return parts

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
        self._last_machines_data = machines_data
        if not machines_data:
            self._content.update(
                Content.assemble(
                    ("No attached machines.\n", "$muted"),
                    ("/remote bootstrap <host>", "$primary"),
                )
            )
            return

        parts: list[str | Content | tuple[str, str]] = []
        for idx, machine in enumerate(machines_data):
            if idx > 0:
                parts.append((Glyphs.RULE * self.RULE_WIDTH + "\n", "$border"))
            parts.extend(self._machine_block(machine))

        with contextlib.suppress(Exception):
            self._content.update(Content.assemble(*parts).rstrip())


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
                Renders updated content with highlighted machine pill.
        """
        self._machines = machines if machines else ["localhost"]
        self._current_index = max(
            0, min(current_index, len(self._machines) - 1)
        )
        self._render_bar()

    def _render_bar(self) -> None:
        """Render selector bar using semantic theme tokens.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Updates widget display.
        """
        parts: list[str | Content | tuple[str, str]] = [
            (" SHELL ", "bold $background on $success"),
            ("  target ", "$muted"),
        ]
        for idx, machine_name in enumerate(self._machines):
            if idx == self._current_index:
                parts.append(
                    (
                        f" {Glyphs.DOT_ON} {machine_name} ",
                        "bold $selection-fg on $selection-bg",
                    )
                )
            else:
                parts.append(
                    (f" {Glyphs.DOT_OFF} {machine_name} ", "$muted")
                )
        parts.append(("   tab/←→ switch host  ·  ^s exit", "$muted"))
        with contextlib.suppress(Exception):
            self.update(Content.assemble(*parts))


class SlashAutocompletePopup(Static):
    """Floating autocomplete popup for interactive slash commands.

    Parameters
    ------------
    None

    Returns
    --------
        SlashAutocompletePopup: SlashAutocompletePopup instance
            Constructed autocomplete popup widget.
    """

    MAX_VISIBLE: ClassVar[int] = 6

    SLASH_COMMANDS: list[tuple[str, str]] = [
        ("/plan", "Preview DAG decomposition without auto-executing"),
        ("/run", "Execute a planned or pending research DAG"),
        ("/view", "Open local NiiVue WebGL2 visualization session"),
        ("/status", "View workspace status, blackboard stats, and tokens"),
        ("/brain", "Manage Obsidian memory vault and search priors"),
        ("/skills", "Browse Tier-0 neuroscience skills catalog"),
        ("/harness", "View or update agent role-to-harness routing"),
        ("/remote", "View, bootstrap, or remove remote compute hosts"),
        ("/machines", "Inspect attached compute nodes and load"),
        ("/jobs", "Monitor or reconcile Slurm/tmux batch jobs"),
        ("/shell", "Run command locally or on remote host"),
        ("/history", "View or clear command and prompt history"),
        ("/theme", "List or switch visual color themes"),
        ("/retry", "Resume a node paused in WAITING_OPERATOR"),
        ("/cancel", "Cancel a paused node in WAITING_OPERATOR"),
        ("/init", "Initialize .neuri/ workspace configuration"),
        ("/clear", "Clear the chat screen (preserves SQLite state)"),
        ("/help", "Show interactive command reference"),
        ("/exit", "Exit the Neuri chat interface"),
    ]

    def __init__(self) -> None:
        """Initialize autocomplete popup.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Initializes popup state.
        """
        super().__init__(id="autocomplete-popup", classes="hidden")
        self._matches: list[tuple[str, str]] = []
        self._selected_index: int = 0

    def show_matches(
        self, matches: list[tuple[str, str]], selected_index: int = 0
    ) -> None:
        """Show matching command suggestions in popup.

        Parameters
        ------------
        matches: list[tuple[str, str]]
            List of (command, description) tuples.
        selected_index: int
            Currently highlighted suggestion index. Defaults to 0.

        Returns
        --------
            None: NoneType object
                Renders matched command list and unhides popup.
        """
        self._matches = matches
        self._selected_index = max(0, min(selected_index, len(matches) - 1))
        self.remove_class("hidden")
        self._render_popup()

    def hide(self) -> None:
        """Hide the autocomplete popup.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Adds hidden class and clears matches.
        """
        self.add_class("hidden")
        self._matches = []
        self._selected_index = 0

    def get_selected_command(self) -> str | None:
        """Return the command string of currently selected suggestion.

        Parameters
        ------------
        None

        Returns
        --------
            str | None: string command or None
                Selected command (e.g. '/status') or None if no matches.
        """
        if self._matches and 0 <= self._selected_index < len(self._matches):
            return self._matches[self._selected_index][0]
        return None

    def select_next(self) -> None:
        """Highlight next suggestion.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Advances selection index.
        """
        if self._matches:
            self._selected_index = (
                self._selected_index + 1
            ) % len(self._matches)
            self._render_popup()

    def select_prev(self) -> None:
        """Highlight previous suggestion.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Backtracks selection index.
        """
        if self._matches:
            self._selected_index = (
                self._selected_index - 1
            ) % len(self._matches)
            self._render_popup()

    def _visible_window(self) -> tuple[int, int]:
        """Compute the slice of matches visible around the selection.

        Parameters
        ------------
        None

        Returns
        --------
            tuple[int, int]: tuple object
                (start, end) indices into the match list.
        """
        start: int = max(0, self._selected_index - self.MAX_VISIBLE + 1)
        end: int = min(len(self._matches), start + self.MAX_VISIBLE)
        return (start, end)

    def _render_popup(self) -> None:
        """Render popup content with active selection highlight.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Updates widget display.
        """
        parts: list[str | Content | tuple[str, str]] = []
        start, end = self._visible_window()
        for idx in range(start, end):
            cmd, desc = self._matches[idx]
            if idx == self._selected_index:
                row_style: str = "$selection-fg on $selection-bg"
                parts.append((f" {cmd:<11}", f"bold {row_style}"))
                parts.append((f" {desc} ", row_style))
            else:
                parts.append((f" {cmd:<11}", "bold $primary"))
                parts.append((f" {desc} ", "$muted"))
            parts.append("\n")
        parts.append(("tab/enter select  ·  ↑↓ navigate  ·  esc close", "$muted"))
        with contextlib.suppress(Exception):
            self.update(Content.assemble(*parts))


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

        # Autocomplete popup navigation
        if (
            chat_app is not None
            and hasattr(chat_app, "_autocomplete_popup")
            and chat_app._autocomplete_popup is not None
            and not chat_app._autocomplete_popup.has_class("hidden")
        ):
            if event.key == "down":
                chat_app._autocomplete_popup.select_next()
                event.prevent_default()
                event.stop()
                return
            elif event.key == "up":
                chat_app._autocomplete_popup.select_prev()
                event.prevent_default()
                event.stop()
                return
            elif event.key in ("tab", "enter"):
                selected_cmd: str | None = (
                    chat_app._autocomplete_popup.get_selected_command()
                )
                if selected_cmd:
                    self.value = selected_cmd + " "
                    self.cursor_position = len(self.value)
                    chat_app._autocomplete_popup.hide()
                    event.prevent_default()
                    event.stop()
                    return
            elif event.key == "escape":
                chat_app._autocomplete_popup.hide()
                event.prevent_default()
                event.stop()
                return

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

        # In shell mode, switch machines via Tab / Shift+Tab or Left/Right arrows
        if chat_app is not None and getattr(chat_app, "is_shell_mode", False):
            if event.key in ("tab", "shift+tab"):
                event.prevent_default()
                event.stop()
                if event.key == "tab":
                    chat_app.action_next_machine()
                else:
                    chat_app.action_prev_machine()
                return
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

    TOKEN_BUDGET: ClassVar[float] = 64000.0
    METER_WIDTH: ClassVar[int] = 6

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
            Optional theme model override. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes widget attributes.
        """
        super().__init__(id="telemetry-bar")
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
        with contextlib.suppress(Exception):
            self.refresh()

    def refresh_theme(self, theme: NeuriTheme | None = None) -> None:
        """Re-render telemetry bar when theme changes.

        Parameters
        ------------
        theme: NeuriTheme | None
            Optional updated theme model. Defaults to None.

        Returns
        --------
            None: NoneType object
                Refreshes telemetry widget display.
        """
        if theme is not None:
            self._custom_theme = theme
        with contextlib.suppress(Exception):
            self.refresh()

    @staticmethod
    def status_style(status: str) -> str:
        """Map a status message to a semantic pill style.

        Parameters
        ------------
        status: str
            Current status text.

        Returns
        --------
            str: string object
                Theme style for the status pill.
        """
        lowered: str = status.lower()
        pill_bg: str = "$warning"
        if lowered == "ready":
            pill_bg = "$success"
        elif "error" in lowered or "circuit" in lowered:
            pill_bg = "$error"
        elif lowered.startswith("shell"):
            pill_bg = "$secondary"
        style: str = f"bold $background on {pill_bg}"
        return style

    def render(self) -> Content:
        """Render the telemetry line using semantic theme tokens.

        Parameters
        ------------
        None

        Returns
        --------
            Content: Content object
                Telemetry content styled by the active theme.
        """
        label: str = "bold $accent"
        sep: tuple[str, str] = (f" {Glyphs.SEP} ", "$border")
        telemetry: Content = Content.assemble(
            ("Harness: ", label),
            (self._harness_id, "$foreground"),
            sep,
            ("Machines: ", label),
            (self.machines_summary, "$foreground"),
            sep,
            ("Tokens: ", label),
            render_meter(
                float(self.tokens_count),
                self.TOKEN_BUDGET,
                self.METER_WIDTH,
                "$tokens",
            ),
            (f" {self.tokens_count:,}", "$tokens"),
            sep,
            ("Cost: ", label),
            (f"${self.cost_usd:.2f}", "$cost"),
            sep,
            ("Status: ", label),
            (f" {self.status_text} ", self.status_style(self.status_text)),
        )
        return telemetry


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

    DEFAULT_PLACEHOLDER: ClassVar[str] = (
        "Type a research prompt or /command (/init, /skills, "
        "/machines, /status, /help, /exit)..."
    )

    CSS = """
    Screen {
        background: $background;
        color: $foreground;
    }

    /* ---- Header ---------------------------------------------------- */
    #header-bar {
        dock: top;
        height: 1;
        background: $background;
        padding: 0 1;
    }
    #workspace-banner {
        width: 1fr;
        height: 1;
        color: $foreground;
    }
    #header-help {
        width: auto;
        height: 1;
    }

    /* ---- Main panels ----------------------------------------------- */
    #main-horizontal {
        height: 1fr;
    }
    #chat-scroll {
        width: 1fr;
        height: 100%;
        padding: 0 1;
        background: $background;
        border: round $border;
        border-title-color: $primary;
        border-title-style: bold;
        border-title-align: left;
        scrollbar-size-vertical: 1;
    }
    #chat-scroll:focus {
        border: round $primary;
    }
    #compute-sidebar {
        width: 34;
        height: 100%;
        background: $background;
        border: round $border;
        border-title-color: $foreground;
        border-title-style: bold;
        border-title-align: left;
        border-subtitle-color: $muted;
        padding: 0 1;
        scrollbar-size-vertical: 1;
    }
    #compute-sidebar.hidden {
        display: none;
    }
    #compute-sidebar-content {
        color: $foreground;
    }

    /* ---- Input stack ----------------------------------------------- */
    #input-container {
        dock: bottom;
        height: auto;
        padding: 0;
        background: $background;
    }
    #telemetry-bar {
        height: 1;
        padding: 0 1;
        background: $background;
        color: $foreground;
    }
    #autocomplete-popup {
        background: $surface;
        color: $foreground;
        border: round $primary;
        padding: 0 1;
        max-height: 9;
    }
    #autocomplete-popup.hidden {
        display: none;
    }
    #machine-selector-bar {
        height: 1;
        padding: 0 1;
        background: $background;
        color: $foreground;
    }
    #machine-selector-bar.hidden {
        display: none;
    }
    #prompt-input {
        border: round $border;
        background: $background;
        color: $foreground;
        padding: 0 1;
    }
    #prompt-input:focus {
        border: round $primary;
    }
    #prompt-input.shell-mode,
    #prompt-input.shell-mode:focus {
        border: round $success;
    }
    #prompt-input > .input--placeholder {
        color: $muted;
    }
    Footer {
        background: $background;
    }

    /* ---- Chat cards ------------------------------------------------ */
    .welcome-card {
        height: auto;
        padding: 1 2;
        margin-bottom: 1;
        border-bottom: solid $border;
    }
    .message-card {
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
        background: $background;
    }
    .message-card-user {
        border-left: outer $primary;
    }
    .message-card-assistant {
        border-left: outer $secondary;
    }
    .message-card-shell {
        border-left: outer $success;
    }
    .card-header {
        height: 1;
    }
    .card-body {
        color: $foreground;
        background: $background;
        padding: 0;
        margin: 0;
    }
    .message-card Markdown {
        padding: 0;
        margin: 0;
        background: $background;
    }
    .message-card Collapsible {
        background: $background;
        border-top: none;
        padding: 0;
    }
    .message-card CollapsibleTitle {
        color: $muted;
        padding: 0;
    }
    .thinking-text {
        color: $muted;
        text-style: italic;
        padding: 0 1;
        border-left: outer $border;
    }
    .shell-command {
        height: auto;
        margin-top: 1;
    }
    .shell-result {
        height: auto;
        margin-bottom: 1;
    }
    .shell-stdout {
        color: $foreground;
    }
    .shell-stderr {
        color: $error;
    }
    .shell-footer {
        height: 1;
    }
    """

    BINDINGS: ClassVar[
        list[Binding | tuple[str, str] | tuple[str, str, str]]
    ] = [
        Binding("ctrl+c", "quit", "Quit", show=False),
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
        self._workspace_dir: Path = (
            workspace_dir if workspace_dir is not None else Path.cwd()
        )
        self._theme_manager: NeuriThemeManager = NeuriThemeManager(
            workspace_dir=self._workspace_dir
        )
        super().__init__()
        self._engine: NeuriSessionEngine = (
            session_engine
            if session_engine is not None
            else NeuriSessionEngine(workspace_dir=self._workspace_dir)
        )
        self._harness_id: str = "agy"
        self._telemetry_bar: TelemetryBar = TelemetryBar(
            harness_id=self._harness_id
        )
        self._compute_sidebar: ComputeSidebar = ComputeSidebar()
        self._is_shell_mode: bool = False
        self._available_machines: list[str] = ["localhost"]
        self._selected_machine_index: int = 0
        self._shell_executor: ShellCommandExecutor = ShellCommandExecutor(
            workspace_dir=self._workspace_dir
        )
        self._machine_selector_bar: MachineSelectorBar = MachineSelectorBar()
        self._autocomplete_popup: SlashAutocompletePopup = (
            SlashAutocompletePopup()
        )
        self._history_manager: PromptHistoryManager = PromptHistoryManager()
        self._engine.subscribe(self._handle_session_event)

    def get_theme_variable_defaults(self) -> dict[str, str]:
        """Provide default custom theme variable tokens for Textual CSS.

        Parameters
        ------------
        None

        Returns
        --------
            dict[str, str]: dict object
                Default mapping of custom Neuri CSS variables.
        """
        default_thm: NeuriTheme = self._theme_manager.get_default_theme()
        defaults: dict[str, str] = default_thm.widget_variables()
        return defaults

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
    def is_mounted(self) -> bool:  # type: ignore[override]
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

    def _banner_content(self) -> Content:
        """Build the one-line header banner content.

        Parameters
        ------------
        None

        Returns
        --------
            Content: Content object
                Brand, workspace, init state, and harness summary.
        """
        is_init: bool = (self._workspace_dir / ".neuri").is_dir()
        state_part: tuple[str, str] = (
            (f"{Glyphs.DOT_ON} initialized", "$success")
            if is_init
            else (f"{Glyphs.DOT_OFF} uninitialized (/init)", "$warning")
        )
        sep: tuple[str, str] = (f" {Glyphs.SEP} ", "$border")
        banner: Content = Content.assemble(
            ("neuri", "bold $foreground"),
            (f" {Glyphs.PROMPT} ", "$muted"),
            ("Workspace: ", "$muted"),
            (self._workspace_dir.name or str(self._workspace_dir),
             "bold $primary"),
            sep,
            state_part,
            sep,
            ("harness ", "$muted"),
            (self._harness_id, "$accent"),
        )
        return banner

    def compose(self) -> ComposeResult:
        """Compose layout widgets for the interactive chat interface.

        Parameters
        ------------
        None

        Returns
        --------
            ComposeResult: ComposeResult generator
                Yields header, chat panel, sidebar, input stack, and footer.
        """
        with Horizontal(id="header-bar"):
            yield Static(self._banner_content(), id="workspace-banner")
            yield Static(
                Content.assemble(("? ", "bold $primary"), ("/help", "$muted")),
                id="header-help",
            )

        with Horizontal(id="main-horizontal"):
            chat_scroll: VerticalScroll = VerticalScroll(id="chat-scroll")
            chat_scroll.border_title = ">> Neuri"
            yield chat_scroll
            yield self._compute_sidebar

        with Container(id="input-container"):
            yield self._telemetry_bar
            yield self._autocomplete_popup
            yield self._machine_selector_bar
            yield PromptInput(
                placeholder=self.DEFAULT_PLACEHOLDER,
                id="prompt-input",
                select_on_focus=False,
            )

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

        scroll_area: VerticalScroll = self.query_one(
            "#chat-scroll", VerticalScroll
        )
        await scroll_area.mount(WelcomeCard(self._workspace_dir))

        # Initial machine query and periodic monitor loop
        self.set_interval(15.0, self.refresh_compute_machines)
        asyncio.create_task(self.refresh_compute_machines())

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle real-time input text changes to drive slash autocomplete.

        Parameters
        ------------
        event: Input.Changed
            Input text change event.

        Returns
        --------
            None: NoneType object
                Updates slash command autocomplete popup.
        """
        val: str = event.value.strip()
        if val.startswith("/") and " " not in val:
            matches: list[tuple[str, str]] = [
                cmd
                for cmd in SlashAutocompletePopup.SLASH_COMMANDS
                if cmd[0].startswith(val)
            ]
            exact_match: bool = any(
                val == c[0] for c in SlashAutocompletePopup.SLASH_COMMANDS
            )
            if matches and not exact_match:
                self._autocomplete_popup.show_matches(
                    matches, selected_index=0
                )
                return
        self._autocomplete_popup.hide()

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
        return self._theme_manager.get_default_theme()

    def apply_theme(self, theme_name: str) -> None:
        """Apply a color theme by name to the Textual user interface.

        All widgets style themselves through theme tokens, so switching the
        Textual theme is enough to restyle everything; only the welcome card
        re-renders because it displays the theme name.

        Parameters
        ------------
        theme_name: str
            Theme name or alias (e.g. 'cyberpunk', 'dark', 'monokai', 'nord').

        Returns
        --------
            None: NoneType object
                Updates active application theme.
        """
        clean_name: str = theme_name.strip().lower()
        if clean_name not in self.available_themes:
            thm: NeuriTheme | None = self._theme_manager.get_theme(clean_name)
            if thm is not None:
                self.register_theme(thm.to_textual_theme())
        if clean_name in self.available_themes:
            self.theme = clean_name
        self._refresh_welcome_cards()

    def _refresh_welcome_cards(self) -> None:
        """Re-render any mounted welcome cards (theme / init state changed).

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Refreshes welcome card widgets.
        """
        with contextlib.suppress(Exception):
            for card in self.query(WelcomeCard):
                card.refresh()

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
            input_widget.placeholder = self.DEFAULT_PLACEHOLDER
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

    async def _run_shell_command(
        self, cmd_val: str, scroll_area: VerticalScroll
    ) -> None:
        """Execute a shell command and mount its command and result cards.

        Parameters
        ------------
        cmd_val: str
            Shell command text to execute.
        scroll_area: VerticalScroll
            Chat canvas to mount cards into.

        Returns
        --------
            None: NoneType object
                Mounts shell cards into the chat canvas.
        """
        target_host: str = self.selected_machine
        self._telemetry_bar.status_text = f"Running on {target_host}..."
        await scroll_area.mount(ShellCommandCard(target_host, cmd_val))
        scroll_area.scroll_end(animate=False)

        try:
            res: ShellExecutionResult = await self._shell_executor.execute(
                command=cmd_val, host=target_host
            )
            await scroll_area.mount(ShellResultCard(res))
        except Exception as exc:
            err_sh_turn: ChatTurn = ChatTurn(
                turn_id=f"err_{int(datetime.now(UTC).timestamp())}",
                role=ChatRole.ASSISTANT,
                content=f"**Shell Execution Error:** `{exc}`",
            )
            await scroll_area.mount(MessageCard(err_sh_turn))
        scroll_area.scroll_end(animate=False)

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

        self._autocomplete_popup.hide()
        self._history_manager.add_entry(val)

        input_widget: Input = event.input
        input_widget.value = ""
        input_widget.disabled = True
        self._telemetry_bar.status_text = "Processing..."

        scroll_area: VerticalScroll = self.query_one(
            "#chat-scroll", VerticalScroll
        )

        is_quick_shell: bool = val.startswith("!") or (
            val.startswith("$") and not val.startswith("$$")
        )
        if self._is_shell_mode or is_quick_shell:
            cmd_val: str = val[1:].strip() if is_quick_shell else val
            try:
                await self._run_shell_command(cmd_val, scroll_area)
            finally:
                input_widget.disabled = False
                input_widget.focus()
                mode_lbl: str = (
                    f"Shell [{self.selected_machine}]"
                    if self._is_shell_mode
                    else "Ready"
                )
                self._telemetry_bar.status_text = mode_lbl
            return

        user_turn: ChatTurn = ChatTurn(
            turn_id=f"u_{int(datetime.now(UTC).timestamp())}",
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
                turn_id=f"err_{int(datetime.now(UTC).timestamp())}",
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
                    or ev.payload.get(
                        "theme_name", NeuriThemeManager.DEFAULT_THEME_NAME
                    )
                )
                self.apply_theme(thm_name)
            elif action == "reload_config":
                banner: Static = self.query_one("#workspace-banner", Static)
                banner.update(self._banner_content())
                self._refresh_welcome_cards()
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
    "ShellCommandCard",
    "ShellResultCard",
    "SlashAutocompletePopup",
    "TelemetryBar",
    "WelcomeCard",
]
