"""Interactive Slash Command Router and Execution Subsystem for Neuri.

Provides structured command dispatch (/init, /skills, /status, /harness,
/retry, /cancel, /clear, /help, /exit) designed for both the terminal chat
interface and future Desktop/Web GUIs.
"""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
import yaml

from neuri.core.blackboard import Blackboard
from neuri.core.config import NeuriConfig, init_project_workspace, load_config
from neuri.core.orchestrator import DAGOrchestrator


class SlashCommandResult(BaseModel):
    """Structured result returned by slash command execution.

    Parameters
    ------------
    command: str
        The slash command that was executed (e.g. '/init', '/skills').
    success: bool
        Whether command execution succeeded.
    markdown_output: str
        Human-readable GitHub-flavored markdown rendered in the chat window.
    data: dict[str, Any]
        Raw structured data payload for programmatic GUI consumption.
    action: str | None
        Optional UI trigger action (e.g. 'clear_chat', 'exit_app', 'reload_config').
        Defaults to None.

    Returns
    --------
        SlashCommandResult: SlashCommandResult instance
            Constructed slash command result model.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    command: str = Field(..., description="Executed slash command")
    success: bool = Field(..., description="Whether command succeeded")
    markdown_output: str = Field(..., description="Formatted markdown message")
    data: dict[str, Any] = Field(
        default_factory=dict, description="Structured payload"
    )
    action: str | None = Field(
        default=None, description="UI trigger action if any"
    )


class SlashCommandRouter:
    """Dispatches user commands starting with '/' to typed handlers.

    Parameters
    ------------
    workspace_dir: Path
        Target workspace directory.
    config: NeuriConfig
        Active configuration instance.
    blackboard: Blackboard
        Persistent SQLite WAL state store.
    orchestrator: DAGOrchestrator
        DAG execution orchestrator.
    skills_index_path: Path | None
        Path to skills/index.yaml catalog. Defaults to None.

    Returns
    --------
        SlashCommandRouter: SlashCommandRouter instance
            Constructed command router.
    """

    SUPPORTED_COMMANDS: list[str] = [
        "/init",
        "/skills",
        "/status",
        "/harness",
        "/retry",
        "/cancel",
        "/clear",
        "/help",
        "/exit",
        "/quit",
    ]

    def __init__(
        self,
        workspace_dir: Path,
        config: NeuriConfig,
        blackboard: Blackboard,
        orchestrator: DAGOrchestrator,
        skills_index_path: Path | None = None,
    ) -> None:
        """Initialize slash command router with workspace dependencies.

        Parameters
        ------------
        workspace_dir: Path
            Target workspace directory.
        config: NeuriConfig
            Active Neuri configuration.
        blackboard: Blackboard
            Active Blackboard instance.
        orchestrator: DAGOrchestrator
            Active DAG orchestrator instance.
        skills_index_path: Path | None
            Catalog file path. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes router state.
        """
        self._workspace_dir: Path = workspace_dir
        self._config: NeuriConfig = config
        self._blackboard: Blackboard = blackboard
        self._orchestrator: DAGOrchestrator = orchestrator
        self._skills_index_path: Path = (
            skills_index_path
            if skills_index_path is not None
            else Path("skills/index.yaml")
        )

    def is_slash_command(self, text: str) -> bool:
        """Check if an input string is formatted as a slash command.

        Parameters
        ------------
        text: str
            Raw user input string.

        Returns
        --------
            bool: boolean object
                True if text starts with '/' followed by non-whitespace.
        """
        stripped: str = text.strip()
        is_cmd: bool = stripped.startswith("/") and len(stripped) > 1
        return is_cmd

    def execute(self, command_line: str) -> SlashCommandResult:
        """Route and execute a slash command string.

        Parameters
        ------------
        command_line: str
            Full command string (e.g. '/init', '/skills bids-standard').

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Outcome of command execution.
        """
        parts: list[str] = command_line.strip().split()
        if not parts:
            return SlashCommandResult(
                command="/",
                success=False,
                markdown_output="No command provided.",
            )

        cmd: str = parts[0].lower()
        args: list[str] = parts[1:]

        if cmd == "/init":
            return self._handle_init()
        elif cmd == "/skills":
            return self._handle_skills(args)
        elif cmd == "/status":
            return self._handle_status()
        elif cmd == "/harness":
            return self._handle_harness(args)
        elif cmd == "/retry":
            return self._handle_retry(args)
        elif cmd == "/cancel":
            return self._handle_cancel(args)
        elif cmd == "/clear":
            return self._handle_clear()
        elif cmd in ("/help", "/?"):
            return self._handle_help()
        elif cmd in ("/exit", "/quit"):
            return self._handle_exit()
        else:
            return SlashCommandResult(
                command=cmd,
                success=False,
                markdown_output=(
                    f"Unknown command: `{cmd}`. Type `/help` to see available "
                    f"commands."
                ),
            )

    def _handle_init(self) -> SlashCommandResult:
        """Initialize .neuri workspace in current directory.

        Parameters
        ------------
        None

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Initialization result card.
        """
        try:
            ws_path: Path = init_project_workspace(self._workspace_dir)
            msg: str = (
                f"### Workspace Initialized\n\n"
                f"Successfully initialized Neuri workspace at:\n"
                f"- Directory: `{ws_path}`\n"
                f"- Configuration: `{ws_path / 'neuri.toml'}`\n"
                f"- Blackboard: `{ws_path / 'state.db'}`\n"
                f"- Provenance Log: `{ws_path / 'execution_history.json'}`\n"
                f"- References Ledger: `{ws_path / 'references.bib'}`\n"
            )
            return SlashCommandResult(
                command="/init",
                success=True,
                markdown_output=msg,
                data={"workspace_path": str(ws_path)},
                action="reload_config",
            )
        except Exception as exc:
            return SlashCommandResult(
                command="/init",
                success=False,
                markdown_output=f"Failed to initialize workspace: {exc}",
            )

    def _handle_skills(self, args: list[str]) -> SlashCommandResult:
        """List or inspect neuroscience skills catalog.

        Parameters
        ------------
        args: list[str]
            Optional skill ID or 'list'.

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Rendered skills table or skill specification card.
        """
        if not self._skills_index_path.is_file():
            return SlashCommandResult(
                command="/skills",
                success=False,
                markdown_output=(
                    f"Skills catalog not found at `{self._skills_index_path}`."
                ),
            )

        try:
            content: str = self._skills_index_path.read_text(encoding="utf-8")
            data: dict[str, Any] = yaml.safe_load(content) or {}
            skills: list[dict[str, Any]] = data.get("skills", [])

            if args and args[0] not in ("list", ""):
                target_id: str = args[0].strip().lower()
                for sk in skills:
                    if str(sk.get("id")).lower() == target_id or target_id in [
                        str(a).lower() for a in sk.get("aliases", [])
                    ]:
                        detail_msg: str = (
                            f"### Skill: {sk.get('name')}\n\n"
                            f"- **ID:** `{sk.get('id')}`\n"
                            f"- **Aliases:** `{sk.get('aliases', [])}`\n"
                            f"- **Description:** {sk.get('description')}\n"
                            f"- **Modalities:** {', '.join(sk.get('modalities', []))}\n"
                            f"- **Triggers:** {', '.join(sk.get('triggers', []))}\n"
                        )
                        return SlashCommandResult(
                            command="/skills",
                            success=True,
                            markdown_output=detail_msg,
                            data=sk,
                        )
                return SlashCommandResult(
                    command="/skills",
                    success=False,
                    markdown_output=f"Skill `{args[0]}` not found in catalog.",
                )

            # Render catalog table
            lines: list[str] = [
                "### Neuroscience Skills Catalog\n",
                "| ID | Name | Modalities | Triggers |",
                "| :--- | :--- | :--- | :--- |",
            ]
            for sk in skills:
                s_id: str = str(sk.get("id"))
                name: str = str(sk.get("name"))
                mods: str = ", ".join(sk.get("modalities", []))
                trigs: str = ", ".join(sk.get("triggers", []))[:35] + "..."
                lines.append(f"| `{s_id}` | {name} | {mods} | {trigs} |")

            table_md: str = "\n".join(lines)
            return SlashCommandResult(
                command="/skills",
                success=True,
                markdown_output=table_md,
                data={"skills_count": len(skills)},
            )
        except Exception as exc:
            return SlashCommandResult(
                command="/skills",
                success=False,
                markdown_output=f"Failed to read skills catalog: {exc}",
            )

    def _handle_status(self) -> SlashCommandResult:
        """Display workspace, remote host, blackboard, and telemetry status.

        Parameters
        ------------
        None

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Rendered status dashboard card.
        """
        is_init: bool = (self._workspace_dir / ".neuri").is_dir()
        remote_host: str = self._config.project.default_remote_host
        harness_default: str = self._config.harness_routing.default_harness

        msg: str = (
            f"### Neuri System Status\n\n"
            f"- **Workspace Directory:** `{self._workspace_dir}`\n"
            f"- **Initialized (.neuri):** `{'Yes' if is_init else 'No (type /init to initialize)'}`\n"
            f"- **Default Remote Host:** `{remote_host}`\n"
            f"- **Default Harness:** `{harness_default}`\n"
            f"- **Max Node Tokens:** `{self._config.budgets.max_node_tokens:,}`\n"
            f"- **Max Workflow Cost:** `${self._config.budgets.max_workflow_cost_usd:.2f}`\n"
        )
        return SlashCommandResult(
            command="/status",
            success=True,
            markdown_output=msg,
            data={
                "workspace_initialized": is_init,
                "remote_host": remote_host,
                "default_harness": harness_default,
            },
        )

    def _handle_harness(self, args: list[str]) -> SlashCommandResult:
        """Display or update role-to-harness routing configuration.

        Parameters
        ------------
        args: list[str]
            Optional [role, harness_id] pair to update.

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Routing table or confirmation card.
        """
        routing: dict[str, str] = self._config.harness_routing.role_map

        if len(args) >= 2:
            role: str = args[0].strip()
            h_id: str = args[1].strip()
            routing[role] = h_id
            msg: str = (
                f"Updated harness routing: Sub-agent role `{role}` is now "
                f"dispatched to harness `{h_id}`."
            )
            return SlashCommandResult(
                command="/harness",
                success=True,
                markdown_output=msg,
                data={"role": role, "harness_id": h_id},
            )

        lines: list[str] = [
            "### Harness Routing Map\n",
            f"**Default Harness:** `{self._config.harness_routing.default_harness}`\n",
            "| Agent Role | Target Harness |",
            "| :--- | :--- |",
        ]
        for r, h in routing.items():
            lines.append(f"| `{r}` | `{h}` |")

        return SlashCommandResult(
            command="/harness",
            success=True,
            markdown_output="\n".join(lines),
            data=dict(routing),
        )

    def _handle_retry(self, args: list[str]) -> SlashCommandResult:
        """Retry a node paused in WAITING_OPERATOR.

        Parameters
        ------------
        args: list[str]
            Arguments containing the node_id to retry.

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Retry outcome card.
        """
        if not args:
            return SlashCommandResult(
                command="/retry",
                success=False,
                markdown_output="Usage: `/retry <node_id>`",
            )

        node_id: str = args[0].strip()
        ok: bool = self._orchestrator.retry_node(node_id)
        if ok:
            msg: str = (
                f"Node `{node_id}` reset to `PENDING` state and queued "
                f"for execution."
            )
            return SlashCommandResult(
                command="/retry",
                success=True,
                markdown_output=msg,
                data={"node_id": node_id, "new_state": "PENDING"},
            )
        return SlashCommandResult(
            command="/retry",
            success=False,
            markdown_output=(
                f"Could not retry node `{node_id}`. Verify that the node "
                f"exists and is currently in WAITING_OPERATOR or FAILED state."
            ),
        )

    def _handle_cancel(self, args: list[str]) -> SlashCommandResult:
        """Cancel a node paused in WAITING_OPERATOR.

        Parameters
        ------------
        args: list[str]
            Arguments containing the node_id to cancel.

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Cancellation outcome card.
        """
        if not args:
            return SlashCommandResult(
                command="/cancel",
                success=False,
                markdown_output="Usage: `/cancel <node_id>`",
            )

        node_id: str = args[0].strip()
        ok: bool = self._orchestrator.cancel_node(node_id)
        if ok:
            return SlashCommandResult(
                command="/cancel",
                success=True,
                markdown_output=f"Node `{node_id}` transitioned to `CANCELLED`.",
                data={"node_id": node_id, "new_state": "CANCELLED"},
            )
        return SlashCommandResult(
            command="/cancel",
            success=False,
            markdown_output=f"Could not cancel node `{node_id}`.",
        )

    def _handle_clear(self) -> SlashCommandResult:
        """Signal frontends to clear the chat transcript.

        Parameters
        ------------
        None

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Clear chat action result.
        """
        return SlashCommandResult(
            command="/clear",
            success=True,
            markdown_output="Chat canvas cleared.",
            action="clear_chat",
        )

    def _handle_help(self) -> SlashCommandResult:
        """Return available slash commands and shortcuts.

        Parameters
        ------------
        None

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Markdown help card.
        """
        help_md: str = (
            "### Neuri Interactive Commands\n\n"
            "| Command | Description |\n"
            "| :--- | :--- |\n"
            "| `/init` | Initialize `.neuri/` workspace configuration and state |\n"
            "| `/skills` | Browse Tier-0 neuroscience skills catalog |\n"
            "| `/skills <id>` | Inspect inputs, triggers, and modalities of a skill |\n"
            "| `/status` | View workspace status, blackboard stats, and token usage |\n"
            "| `/harness` | View or update agent role-to-harness routing |\n"
            "| `/retry <node_id>` | Resume a node paused in WAITING_OPERATOR |\n"
            "| `/cancel <node_id>` | Cancel a paused node in WAITING_OPERATOR |\n"
            "| `/clear` | Clear the chat screen (preserves SQLite state) |\n"
            "| `/help` | Show this command reference |\n"
            "| `/exit` | Exit the Neuri chat interface |\n\n"
            "**Natural Language Prompting:** Enter any research prompt to decompose "
            "into a multi-agent DAG and execute across connected harnesses."
        )
        return SlashCommandResult(
            command="/help",
            success=True,
            markdown_output=help_md,
        )

    def _handle_exit(self) -> SlashCommandResult:
        """Signal frontend application to exit cleanly.

        Parameters
        ------------
        None

        Returns
        --------
            SlashCommandResult: SlashCommandResult instance
                Exit action result.
        """
        return SlashCommandResult(
            command="/exit",
            success=True,
            markdown_output="Exiting Neuri session. Goodbye!",
            action="exit_app",
        )


__all__: list[str] = [
    "SlashCommandResult",
    "SlashCommandRouter",
]
