"""UI-Agnostic NeuriSessionEngine for Terminal Chat and Future GUIs.

Decouples all conversational turns, slash-command routing, DAG execution,
and live telemetry event streaming from presentation frontends, enabling
seamless pluggability of Textual TUI, Tauri Desktop GUI, or Web interfaces.
"""

import asyncio
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import uuid

from neuri.core.blackboard import Blackboard
from neuri.core.config import NeuriConfig, load_config
from neuri.core.orchestrator import DAGOrchestrator
from neuri.core.schemas import (
    ChatRole,
    ChatTurn,
    NeuriTaskResult,
    SessionEvent,
    SessionEventType,
    TaskNode,
    TelemetryEvent,
)
from neuri.core.slash_commands import SlashCommandResult, SlashCommandRouter


class NeuriSessionEngine:
    """Core UI-agnostic session engine managing turns and dispatching events.

    Provides a clean, async event bus architecture. Frontends (such as
    Textual TUI, WebSockets, or Desktop GUI) attach via event subscription
    and invoke `submit_user_input` without embedding business logic.

    Parameters
    ------------
    workspace_dir: Path | None
        Target workspace root directory. Defaults to current working directory.
    config: NeuriConfig | None
        Loaded Neuri configuration. Defaults to None (loaded automatically).
    blackboard: Blackboard | None
        Persistent SQLite WAL Blackboard. Defaults to None (auto-initialized).

    Returns
    --------
        NeuriSessionEngine: NeuriSessionEngine instance
            Constructed session engine.
    """

    def __init__(
        self,
        workspace_dir: Path | None = None,
        config: NeuriConfig | None = None,
        blackboard: Blackboard | None = None,
        model: str | None = None,
        harness: str | None = None,
    ) -> None:
        """Initialize session engine and instantiate core subsystems.

        Parameters
        ------------
        workspace_dir: Path | None
            Workspace directory. Defaults to Path.cwd().
        config: NeuriConfig | None
            Configuration model. Defaults to None.
        blackboard: Blackboard | None
            Blackboard store. Defaults to None.
        model: str | None
            Active AI model override across harnesses. Defaults to None.
        harness: str | None
            Active AI harness override across roles. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes engine state and event listener bus.
        """
        self._workspace_dir: Path = (
            workspace_dir if workspace_dir is not None else Path.cwd()
        )
        self._session_id: str = f"sess_{uuid.uuid4().hex[:12]}"
        self._config: NeuriConfig = (
            config if config is not None else load_config(self._workspace_dir)
        )
        if harness is not None and harness.strip():
            h_clean: str = harness.strip().lower()
            if h_clean == "antigravity":
                canonical_h: str = "agy"
            elif h_clean == "ollama_local":
                canonical_h = "ollama"
            else:
                canonical_h = h_clean
            self._config.project.default_harness = canonical_h
            if isinstance(self._config.harness_routing, dict):
                for r_cfg in self._config.harness_routing.values():
                    r_cfg.harness = canonical_h

        explicit_model: str | None = None
        if model is not None and model.strip():
            explicit_model = model.strip()
            self._config.project.default_model = explicit_model
            if isinstance(self._config.harness_routing, dict):
                for r_cfg in self._config.harness_routing.values():
                    r_cfg.model = explicit_model

        db_path: Path = self._resolve_db_path()
        self._blackboard: Blackboard = (
            blackboard if blackboard is not None else Blackboard(db_path)
        )
        self._orchestrator: DAGOrchestrator = DAGOrchestrator(
            blackboard=self._blackboard,
            config=self._config,
        )
        if explicit_model is None:
            resolved_m: str | None = self._orchestrator.resolve_active_model(
                self.harness
            )
            if resolved_m is not None:
                self._config.project.default_model = resolved_m
                if isinstance(self._config.harness_routing, dict):
                    for r_cfg in self._config.harness_routing.values():
                        r_cfg.model = resolved_m
        self._slash_router: SlashCommandRouter = SlashCommandRouter(
            workspace_dir=self._workspace_dir,
            config=self._config,
            blackboard=self._blackboard,
            orchestrator=self._orchestrator,
        )

        self._listeners: list[Callable[[SessionEvent], None]] = []
        self._turns: list[ChatTurn] = []
        self._accumulated_thinking: list[str] = []

    def _resolve_db_path(self) -> Path:
        """Resolve the SQLite database path based on workspace state.

        Parameters
        ------------
        None

        Returns
        --------
            Path: Path object
                Path to state.db.
        """
        ws_dot_dir: Path = self._workspace_dir / ".neuri"
        if ws_dot_dir.is_dir():
            path: Path = ws_dot_dir / "state.db"
            return path
        home_dot_dir: Path = Path.home() / ".neuri"
        if home_dot_dir.is_dir():
            path_home: Path = home_dot_dir / "state.db"
            return path_home
        fallback: Path = self._workspace_dir / ".neuri_tmp_state.db"
        return fallback

    @property
    def session_id(self) -> str:
        """Active session identifier.

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                Session ID.
        """
        s_id: str = self._session_id
        return s_id

    @property
    def config(self) -> NeuriConfig:
        """Active session configuration model.

        Parameters
        ------------
        None

        Returns
        --------
            NeuriConfig: NeuriConfig instance
                Configuration model.
        """
        cfg: NeuriConfig = self._config
        return cfg

    @property
    def harness(self) -> str:
        """Active AI harness identifier applied across all roles.

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                Active harness ID string.
        """
        h_id: str = getattr(self._config.project, "default_harness", "agy")
        return h_id

    @property
    def model(self) -> str | None:
        """Active AI model identifier applied across all roles.

        Parameters
        ------------
        None

        Returns
        --------
            str | None: string or None
                Model name string or None if vendor default.
        """
        m_id: str | None = getattr(self._config.project, "default_model", None)
        return m_id

    @property
    def turns(self) -> list[ChatTurn]:
        """Shallow copy of accumulated conversation history turns.

        Parameters
        ------------
        None

        Returns
        --------
            list[ChatTurn]: list object
                Recorded chat turns.
        """
        res: list[ChatTurn] = list(self._turns)
        return res

    def subscribe(self, listener: Callable[[SessionEvent], None]) -> None:
        """Subscribe a callable listener to receive live SessionEvents.

        Parameters
        ------------
        listener: Callable[[SessionEvent], None]
            Event handler callback.

        Returns
        --------
            None: NoneType object
                Registers listener.
        """
        if listener not in self._listeners:
            self._listeners.append(listener)

    def unsubscribe(self, listener: Callable[[SessionEvent], None]) -> None:
        """Unsubscribe a previously registered event listener.

        Parameters
        ------------
        listener: Callable[[SessionEvent], None]
            Event handler callback to remove.

        Returns
        --------
            None: NoneType object
                Removes listener.
        """
        if listener in self._listeners:
            self._listeners.remove(listener)

    def emit_event(
        self, event_type: SessionEventType, payload: dict[str, Any]
    ) -> SessionEvent:
        """Emit a typed SessionEvent to all subscribed frontend listeners.

        Parameters
        ------------
        event_type: SessionEventType
            Type category of session event.
        payload: dict[str, Any]
            Typed dictionary payload.

        Returns
        --------
            SessionEvent: SessionEvent instance
                The dispatched event object.
        """
        ev: SessionEvent = SessionEvent(
            event_id=f"sev_{uuid.uuid4().hex[:12]}",
            session_id=self._session_id,
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            payload=payload,
        )
        for listener in self._listeners:
            try:
                listener(ev)
            except Exception:
                pass
        return ev

    async def submit_user_input(self, text: str) -> ChatTurn:
        """Process user input (slash command or natural language research prompt).

        Parameters
        ------------
        text: str
            Raw user input string.

        Returns
        --------
            ChatTurn: ChatTurn instance
                The resulting assistant or system chat turn.
        """
        stripped: str = text.strip()

        # 1. Record user turn
        user_turn: ChatTurn = ChatTurn(
            turn_id=f"turn_{uuid.uuid4().hex[:12]}",
            role=ChatRole.USER,
            content=stripped,
        )
        self._turns.append(user_turn)
        self.emit_event(
            SessionEventType.USER_MESSAGE,
            {"turn_id": user_turn.turn_id, "content": stripped},
        )

        # 2. Check if slash command
        if self._slash_router.is_slash_command(stripped):
            return await self._process_slash_command(stripped)

        # 3. Otherwise, process natural language prompt via DAG orchestrator
        return await self._process_research_prompt(stripped)

    async def _process_slash_command(self, command_line: str) -> ChatTurn:
        """Execute slash command and emit result events.

        Parameters
        ------------
        command_line: str
            Slash command string.

        Returns
        --------
            ChatTurn: ChatTurn instance
                Assistant chat turn rendering slash command output.
        """
        cmd_res: SlashCommandResult = (
            await self._slash_router.execute_async(command_line)
        )

        # If action requested (e.g. reload_config or change_theme)
        if cmd_res.action in ("reload_config", "change_theme"):
            self._config = load_config(self._workspace_dir)
            db_path: Path = self._resolve_db_path()
            self._blackboard = Blackboard(db_path)
            self._orchestrator = DAGOrchestrator(
                blackboard=self._blackboard,
                config=self._config,
            )

        # Emit status update event
        self.emit_event(
            SessionEventType.STATUS_UPDATE,
            {
                "command": cmd_res.command,
                "success": cmd_res.success,
                "action": cmd_res.action,
                "data": cmd_res.data,
            },
        )

        if cmd_res.action == "resume_workflow":
            wf_id: str | None = cmd_res.data.get("workflow_id")
            if wf_id:
                confirm_turn: ChatTurn = ChatTurn(
                    turn_id=f"turn_{uuid.uuid4().hex[:12]}",
                    role=ChatRole.ASSISTANT,
                    content=cmd_res.markdown_output,
                )
                self._turns.append(confirm_turn)

                results: list[NeuriTaskResult] = (
                    await self._orchestrator.execute_workflow(
                        workflow_id=wf_id,
                        on_event=self._forward_telemetry,
                    )
                )
                return self._format_workflow_results(wf_id, results)

        assistant_turn: ChatTurn = ChatTurn(
            turn_id=f"turn_{uuid.uuid4().hex[:12]}",
            role=ChatRole.ASSISTANT,
            content=cmd_res.markdown_output,
        )
        self._turns.append(assistant_turn)
        return assistant_turn

    async def execute_shell_command(
        self, command: str, host: str = "localhost"
    ) -> ChatTurn:
        """Execute a shell command locally or remotely and append to session.

        Parameters
        ------------
        command: str
            Shell command string to execute.
        host: str
            Target machine alias ('localhost' or remote host).
            Defaults to 'localhost'.

        Returns
        --------
            ChatTurn: ChatTurn instance
                Assistant chat turn containing formatted command output.
        """
        from neuri.remote.shell_executor import (
            ShellCommandExecutor,
            ShellExecutionResult,
        )

        user_turn: ChatTurn = ChatTurn(
            turn_id=f"u_sh_{uuid.uuid4().hex[:8]}",
            role=ChatRole.USER,
            content=f"**[{host}]** `$ {command}`",
        )
        self._turns.append(user_turn)

        executor: ShellCommandExecutor = ShellCommandExecutor(
            workspace_dir=self._workspace_dir
        )
        res: ShellExecutionResult = await executor.execute(
            command=command, host=host
        )
        card_md: str = executor.format_markdown_card(res)

        assistant_turn: ChatTurn = ChatTurn(
            turn_id=f"a_sh_{uuid.uuid4().hex[:8]}",
            role=ChatRole.ASSISTANT,
            content=card_md,
        )
        self._turns.append(assistant_turn)
        return assistant_turn

    async def _process_research_prompt(self, prompt: str) -> ChatTurn:
        """Decompose prompt into DAG and orchestrate execution.

        Parameters
        ------------
        prompt: str
            Natural language prompt.

        Returns
        --------
            ChatTurn: ChatTurn instance
                Consolidated assistant response turn.
        """
        self._accumulated_thinking.clear()

        # Step 1: Plan workflow
        wf_id: str = self._orchestrator.plan_workflow_from_prompt(prompt)
        self.emit_event(
            SessionEventType.STATUS_UPDATE,
            {
                "status": "workflow_planned",
                "workflow_id": wf_id,
                "message": f"Planned research workflow `{wf_id}`.",
            },
        )

        # Step 2: Execute ready nodes wave-by-wave
        results: list[NeuriTaskResult] = (
            await self._orchestrator.execute_workflow(
                workflow_id=wf_id,
                on_event=self._forward_telemetry,
            )
        )

        return self._format_workflow_results(wf_id, results)

    def _format_workflow_results(
        self, wf_id: str, results: list[NeuriTaskResult]
    ) -> ChatTurn:
        """Format aggregated node execution results into an assistant ChatTurn.

        Parameters
        ------------
        wf_id: str
            Workflow identifier.
        results: list[NeuriTaskResult]
            List of node task results.

        Returns
        --------
            ChatTurn: ChatTurn instance
                Assistant turn with formatted execution summary and telemetry.
        """
        response_blocks: list[str] = []
        all_success: bool = True
        total_tokens: int = 0
        total_cost: float = 0.0

        for res in results:
            total_tokens += res.total_tokens
            total_cost += res.cost_usd
            if not res.success:
                all_success = False
            if len(results) == 1 and res.success:
                response_blocks.append(res.summary)
            else:
                status_symbol: str = "✓" if res.success else "✗"
                response_blocks.append(
                    f"#### {status_symbol} Node `{res.node_id}`\n\n{res.summary}"
                )
            if res.error_message:
                response_blocks.append(f"\n*Error:* `{res.error_message}`")

        response_blocks.append(
            f"\n---\n*Workflow `{wf_id}` • {total_tokens:,} tokens "
            f"(${total_cost:.4f} USD)*"
        )
        summary_lines: list[str] = response_blocks

        dot_neuri: Path = self._workspace_dir / ".neuri"
        if dot_neuri.is_dir():
            try:
                self._blackboard.export_provenance_log(
                    dot_neuri / "execution_history.json",
                    workflow_id=wf_id,
                )
            except Exception:
                pass

        final_content: str = "\n".join(summary_lines)
        self.emit_event(
            SessionEventType.WORKFLOW_COMPLETED,
            {
                "workflow_id": wf_id,
                "success": all_success,
                "total_tokens": total_tokens,
                "cost_usd": total_cost,
            },
        )

        combined_thinking: str | None = (
            "".join(self._accumulated_thinking)
            if self._accumulated_thinking
            else None
        )
        assistant_turn: ChatTurn = ChatTurn(
            turn_id=f"turn_{uuid.uuid4().hex[:12]}",
            role=ChatRole.ASSISTANT,
            content=final_content,
            thinking_trace=combined_thinking,
            workflow_id=wf_id,
        )
        self._turns.append(assistant_turn)
        return assistant_turn

    def _forward_telemetry(self, ev: TelemetryEvent) -> None:
        """Forward TelemetryEvents from harness stream to frontend.

        Parameters
        ------------
        ev: TelemetryEvent
            Telemetry event emitted by harness.

        Returns
        --------
            None: NoneType object
                Dispatches corresponding session event.
        """
        if ev.event_type == "content_delta" and ev.content_text:
            self.emit_event(
                SessionEventType.ASSISTANT_CHUNK,
                {
                    "workflow_id": ev.workflow_id,
                    "node_id": ev.node_id,
                    "content_delta": ev.content_text,
                },
            )
        elif ev.event_type == "thinking_delta" and ev.thinking_text:
            self._accumulated_thinking.append(ev.thinking_text)
            self.emit_event(
                SessionEventType.THINKING_CHUNK,
                {
                    "workflow_id": ev.workflow_id,
                    "node_id": ev.node_id,
                    "thinking_delta": ev.thinking_text,
                },
            )
        elif ev.event_type == "tool_lifecycle":
            self.emit_event(
                SessionEventType.TOOL_CALL_UPDATE,
                {
                    "workflow_id": ev.workflow_id,
                    "node_id": ev.node_id,
                    "tool_name": ev.tool_name,
                    "tool_host": ev.tool_host,
                    "tool_status": ev.tool_status,
                    "duration_ms": ev.duration_ms,
                },
            )
        elif ev.event_type == "token_usage":
            self.emit_event(
                SessionEventType.STATUS_UPDATE,
                {
                    "action": "token_increment",
                    "tokens": ev.output_tokens,
                    "cost_usd": ev.estimated_cost_usd,
                },
            )
        elif ev.event_type == "circuit_breaker":
            self.emit_event(
                SessionEventType.CIRCUIT_BREAKER_TRIGGERED,
                {
                    "workflow_id": ev.workflow_id,
                    "node_id": ev.node_id,
                    "reason": ev.breaker_reason,
                },
            )
        elif ev.event_type == "raw_stream" and ev.raw_text:
            self.emit_event(
                SessionEventType.STATUS_UPDATE,
                {
                    "action": "raw_stream",
                    "workflow_id": ev.workflow_id,
                    "node_id": ev.node_id,
                    "raw_text": ev.raw_text,
                },
            )

    def clear_turns(self) -> None:
        """Clear conversation turns in session memory.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Clears internal turn history.
        """
        self._turns.clear()


__all__: list[str] = [
    "NeuriSessionEngine",
]
