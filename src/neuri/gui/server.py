"""HTTP, Server-Sent Events, and REST API bridge for Neuri Studio GUI.

Embeds an HTTP server wrapping NeuriSessionEngine, NiiVueBridge, Blackboard,
and ShellCommandExecutor to serve the 4-zone GUI interface with real-time SSE
event streaming and full parity with terminal functionality.
"""

from collections.abc import Callable
import contextlib
from datetime import datetime, timezone
import json
import mimetypes
from pathlib import Path
import queue
import re
import socket
from socketserver import ThreadingMixIn
import tempfile
import threading
import time
from typing import Any
from urllib.parse import parse_qs, urlparse
import uuid

from neuri.core.blackboard import Blackboard
from neuri.core.schemas import (
    ChatTurn,
    NeuriTaskEnvelope,
    SessionEvent,
    SessionEventType,
    TaskEdge,
    TaskNode,
    TaskState,
)
from neuri.core.session import NeuriSessionEngine
from neuri.gui.introspect import NeuriIntrospector
from neuri.remote.monitor import RemoteHostMonitor
from neuri.remote.shell_executor import (
    ShellCommandExecutor,
    ShellExecutionResult,
)
from neuri.ui.history import PromptHistoryManager
from neuri.ui.theme import NeuriTheme, NeuriThemeManager
from neuri.viewer.local_explorer import LocalFileExplorer
from neuri.viewer.niivue_bridge import NiiVueBridgeHandler, NiiVueHTTPServer


class NeuriGUIServer(ThreadingMixIn, NiiVueHTTPServer):
    """Threading HTTP server carrying Neuri session engine and state for GUI.

    Parameters
    ------------
    server_address: tuple[str, int]
        Host address and port tuple.
    session_engine: NeuriSessionEngine
        Active session engine instance.
    theme_manager: NeuriThemeManager
        Active theme manager utility.
    history_manager: PromptHistoryManager
        Command prompt history manager.
    static_dir: Path
        Root directory containing GUI static HTML/CSS/JS assets.

    Returns
    --------
        NeuriGUIServer: NeuriGUIServer instance
            Constructed GUI server with shared session context.
    """

    daemon_threads: bool = True

    def __init__(
        self,
        server_address: tuple[str, int],
        session_engine: NeuriSessionEngine,
        theme_manager: NeuriThemeManager,
        history_manager: PromptHistoryManager,
        static_dir: Path,
    ) -> None:
        """Initialize GUI server and configure subscriber queue bus.

        Parameters
        ------------
        server_address: tuple[str, int]
            Host address and port tuple.
        session_engine: NeuriSessionEngine
            Active session engine instance.
        theme_manager: NeuriThemeManager
            Active theme manager utility.
        history_manager: PromptHistoryManager
            Command prompt history manager.
        static_dir: Path
            Path to static assets directory.

        Returns
        --------
            None: NoneType object
                Initializes server state.
        """
        super().__init__(server_address, NeuriGUIHandler)
        self.session_engine: NeuriSessionEngine = session_engine
        self.theme_manager: NeuriThemeManager = theme_manager
        self.history_manager: PromptHistoryManager = history_manager
        self.introspector: NeuriIntrospector = NeuriIntrospector()
        self.static_dir: Path = static_dir.resolve()
        self.event_queues: list[queue.Queue[str]] = []
        self._queue_lock: threading.Lock = threading.Lock()
        self._is_running: bool = False
        self.allowed_roots: list[Path] = [
            self.session_engine._workspace_dir.resolve(),
            Path.cwd().resolve(),
            Path.home().resolve(),
            Path(tempfile.gettempdir()).resolve(),
            (Path.home() / ".neuri").resolve(),
        ]

        # Register event forwarder on session engine
        self.session_engine.subscribe(self._on_session_event)

    def _on_session_event(self, event: SessionEvent) -> None:
        """Broadcast session events to all active SSE client queues.

        Parameters
        ------------
        event: SessionEvent
            Dispatched session event instance.

        Returns
        --------
            None: NoneType object
                Enqueues event payload.
        """
        payload: dict[str, Any] = {
            "event_id": event.event_id,
            "session_id": event.session_id,
            "event_type": event.event_type.value,
            "timestamp": event.timestamp.isoformat(),
            "payload": event.payload,
        }
        msg: str = f"data: {json.dumps(payload)}\n\n"
        with self._queue_lock:
            dead_queues: list[queue.Queue[str]] = []
            for q in self.event_queues:
                try:
                    q.put_nowait(msg)
                except Exception:
                    dead_queues.append(q)
            for dq in dead_queues:
                if dq in self.event_queues:
                    self.event_queues.remove(dq)

    def add_sse_queue(self) -> queue.Queue[str]:
        """Register a new client queue for Server-Sent Events.

        Parameters
        ------------
        None

        Returns
        --------
            queue.Queue[str]: Queue object
                Thread-safe message queue for SSE frames.
        """
        q: queue.Queue[str] = queue.Queue(maxsize=500)
        with self._queue_lock:
            self.event_queues.append(q)
        return q

    def remove_sse_queue(self, q: queue.Queue[str]) -> None:
        """Deregister an SSE client queue upon disconnection.

        Parameters
        ------------
        q: queue.Queue[str]
            Queue to remove.

        Returns
        --------
            None: NoneType object
                Removes queue reference.
        """
        with self._queue_lock:
            if q in self.event_queues:
                self.event_queues.remove(q)


class NeuriGUIHandler(NiiVueBridgeHandler):
    """HTTP request handler routing GUI static files, SSE, and REST endpoints.

    Parameters
    ------------
    request: Any
        Underlying socket connection request.
    client_address: tuple[str, int]
        Tuple of client IP and port.
    server: NeuriGUIServer
        Parent GUI HTTP server instance.

    Returns
    --------
        NeuriGUIHandler: NeuriGUIHandler instance
            Constructed handler instance.
    """

    server: NeuriGUIServer

    def handle_get(self) -> None:
        """Handle incoming GET requests for GUI assets, SSE, state, and NiiVue.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Sends HTTP response.
        """
        parsed_url = urlparse(self.path)
        path: str = parsed_url.path

        if path in ("/", "/index.html"):
            self._serve_gui_index()
        elif path in ("/viewer", "/viewer/", "/viewer/index.html"):
            self._serve_static_index()
        elif path.startswith(("/css/", "/js/", "/static/")):
            self._serve_gui_static(path)
        elif path == "/api/v1/events":
            self._handle_sse_stream()
        elif path == "/api/v1/state":
            self._handle_get_state()
        elif path == "/api/v1/dag":
            self._handle_get_dag()
        elif path == "/api/v1/themes":
            self._handle_get_themes()
        elif path == "/api/v1/history":
            self._handle_get_history()
        elif path == "/api/v1/machines":
            self._handle_get_machines()
        elif path == "/api/v1/introspect":
            self._handle_get_introspect()
        elif path == "/api/v1/volumes":
            self._handle_get_volumes()
        else:
            # Delegate all standard NiiVue endpoints (/api/scene, /api/file, etc.)
            super().handle_get()

    def handle_post(self) -> None:
        """Handle incoming POST requests for user input, shell commands, and DAG.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Processes payload and sends JSON response.
        """
        parsed_url = urlparse(self.path)
        path: str = parsed_url.path

        if path == "/api/v1/input":
            self._handle_post_input()
        elif path == "/api/v1/shell":
            self._handle_post_shell()
        elif path == "/api/v1/themes":
            self._handle_post_theme()
        elif path in ("/api/v1/dag/node", "/api/v1/dag/node/edit"):
            self._handle_post_dag_node()
        elif path == "/api/v1/dag/node/new":
            self._handle_post_dag_node_new()
        elif path == "/api/v1/history/clear":
            self._handle_post_history_clear()
        else:
            # Delegate NiiVue endpoints (/api/scene, /api/scene/selection, etc.)
            super().handle_post()

    do_GET = handle_get
    do_POST = handle_post

    def _serve_gui_index(self) -> None:
        """Serve index.html application shell.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Sends HTML document.
        """
        index_file: Path = self.server.static_dir / "index.html"
        if not index_file.is_file():
            self.send_error(404, "GUI index.html not found.")
            return

        content: bytes = index_file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _serve_gui_static(self, req_path: str) -> None:
        """Serve static JS or CSS asset from GUI static directory.

        Parameters
        ------------
        req_path: str
            Relative URL path to requested asset.

        Returns
        --------
            None: NoneType object
                Sends static file bytes.
        """
        clean_rel: str = req_path.lstrip("/")
        if clean_rel.startswith("static/"):
            clean_rel = clean_rel[len("static/") :]

        target_file: Path = (self.server.static_dir / clean_rel).resolve()
        if not target_file.is_file() or not target_file.is_relative_to(
            self.server.static_dir
        ):
            self.send_error(404, "Asset Not Found")
            return

        mime_type, _ = mimetypes.guess_type(str(target_file))
        content: bytes = target_file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def _handle_sse_stream(self) -> None:
        """Handle persistent Server-Sent Events connection.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Maintains streaming HTTP response until disconnect.
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", self._get_cors_origin())
        self.end_headers()

        q: queue.Queue[str] = self.server.add_sse_queue()

        # Send initial connection handshake
        init_msg: str = (
            f"data: {json.dumps({'event_type': 'connected', 'status': 'ready'})}\n\n"
        )
        try:
            self.wfile.write(init_msg.encode("utf-8"))
            self.wfile.flush()
        except Exception:
            self.server.remove_sse_queue(q)
            return

        try:
            while True:
                try:
                    msg: str = q.get(timeout=15.0)
                    self.wfile.write(msg.encode("utf-8"))
                    self.wfile.flush()
                except queue.Empty:
                    # Send keep-alive ping
                    ping: str = ": ping\n\n"
                    self.wfile.write(ping.encode("utf-8"))
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            self.server.remove_sse_queue(q)

    def _send_json_response(
        self, payload: dict[str, Any], status: int = 200
    ) -> None:
        """Send a JSON payload with standard CORS headers.

        Parameters
        ------------
        payload: dict[str, Any]
            Dictionary response payload.
        status: int
            HTTP response status code. Defaults to 200.

        Returns
        --------
            None: NoneType object
                Sends serialized response.
        """
        body: bytes = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", self._get_cors_origin())
        self.end_headers()
        self.wfile.write(body)

    def _read_json_payload(self) -> dict[str, Any]:
        """Read and parse incoming JSON request body.

        Parameters
        ------------
        None

        Returns
        --------
            dict[str, Any]: dict object
                Parsed request dictionary or empty dict on failure.
        """
        try:
            length: int = int(self.headers.get("Content-Length", 0))
            if length <= 0:
                return {}
            data: bytes = self.rfile.read(length)
            parsed: dict[str, Any] = json.loads(data.decode("utf-8"))
            return parsed
        except Exception:
            return {}

    def _handle_get_state(self) -> None:
        """Return master state snapshot for workspace, turns, and telemetry.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Sends state response.
        """
        se: NeuriSessionEngine = self.server.session_engine
        active_theme_name: str = self.server.theme_manager.get_active_theme_name()
        active_theme: NeuriTheme = self.server.theme_manager.get_theme(
            active_theme_name, fallback_to_default=True
        ) or self.server.theme_manager.get_default_theme()

        turns_data: list[dict[str, Any]] = [
            {
                "turn_id": t.turn_id,
                "role": t.role.value,
                "content": t.content,
                "thinking_trace": t.thinking_trace,
                "timestamp": t.timestamp.isoformat(),
                "node_id": t.node_id,
                "workflow_id": t.workflow_id,
            }
            for t in se.turns
        ]

        active_nodes: list[dict[str, Any]] = []
        workflows_list: list[dict[str, Any]] = []
        with contextlib.suppress(Exception):
            workflows_list = se._blackboard.list_workflows()
            nodes_models: list[TaskNode] = se._blackboard.list_nodes(
                se.current_workflow_id
            )
            for n in nodes_models:
                active_nodes.append({
                    "node_id": n.node_id,
                    "workflow_id": n.workflow_id,
                    "agent_role": n.agent_role,
                    "harness_id": n.harness_id,
                    "state": (
                        n.state.value
                        if hasattr(n.state, "value")
                        else str(n.state)
                    ),
                    "instruction": n.envelope.task_instruction if n.envelope else "",
                    "attempt": n.attempt,
                    "error_message": getattr(n, "error_message", None),
                })

        snapshot: dict[str, Any] = {
            "session_id": se.session_id,
            "workspace_dir": str(se._workspace_dir),
            "workspace_name": se._workspace_dir.name or str(se._workspace_dir),
            "harness": se.harness,
            "model": se.model or "default",
            "active_theme": active_theme.to_dict(),
            "current_workflow_id": se.current_workflow_id,
            "turns": turns_data,
            "workflows": workflows_list,
            "active_nodes": active_nodes,
        }
        self._send_json_response(snapshot)

    def _handle_get_dag(self) -> None:
        """Return DAG nodes and dependency edges for active workflow.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Sends DAG JSON response.
        """
        se: NeuriSessionEngine = self.server.session_engine
        wf_id: str | None = se.current_workflow_id
        if not wf_id and hasattr(se, "_slash_router"):
            wf_id = getattr(se._slash_router, "_last_planned_workflow_id", None)

        nodes_list: list[dict[str, Any]] = []
        edges_list: list[dict[str, Any]] = []

        with contextlib.suppress(Exception):
            if not wf_id:
                wf_dicts: list[dict[str, Any]] = (
                    se._blackboard.list_workflows()
                )
                if wf_dicts:
                    wf_id = str(wf_dicts[-1].get("workflow_id", "")) or None

            if wf_id:
                raw_nodes = se._blackboard.get_nodes_by_workflow(wf_id)
                raw_edges = se._blackboard.get_edges(wf_id)
            else:
                raw_nodes = se._blackboard.list_nodes()
                raw_edges = []

            for n in raw_nodes:
                instr: str = (
                    n.envelope.task_instruction if n.envelope else ""
                )
                mdl: str | None = (
                    n.envelope.model if n.envelope else None
                )
                nodes_list.append({
                    "node_id": n.node_id,
                    "workflow_id": n.workflow_id,
                    "agent_role": n.agent_role,
                    "harness_id": n.harness_id,
                    "state": (
                        n.state.value
                        if hasattr(n.state, "value")
                        else str(n.state)
                    ),
                    "instruction": instr,
                    "model": mdl,
                    "attempt": n.attempt,
                    "error_message": getattr(n, "error_message", None),
                })

            for e in raw_edges:
                from_id: str = str(
                    getattr(
                        e, "parent_node_id", getattr(e, "from_node_id", "")
                    )
                )
                to_id: str = str(
                    getattr(
                        e, "child_node_id", getattr(e, "to_node_id", "")
                    )
                )
                edges_list.append({
                    "from_node_id": from_id,
                    "to_node_id": to_id,
                    "artifact_id": getattr(e, "artifact_id", None),
                })

        self._send_json_response({
            "workflow_id": wf_id,
            "nodes": nodes_list,
            "edges": edges_list,
        })

    def _handle_get_themes(self) -> None:
        """Return all available themes and active theme name.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Sends themes JSON response.
        """
        tm: NeuriThemeManager = self.server.theme_manager
        available: list[NeuriTheme] = tm.list_available_themes()
        active_name: str = tm.get_active_theme_name()

        payload: dict[str, Any] = {
            "active_theme": active_name,
            "themes": [t.to_dict() for t in available],
        }
        self._send_json_response(payload)

    def _handle_get_history(self) -> None:
        """Return prompt and command history list.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Sends history list JSON response.
        """
        entries: list[str] = list(self.server.history_manager.entries)
        self._send_json_response({"entries": entries})

    def _handle_get_machines(self) -> None:
        """Poll machine load, cores, and Slurm jobs across compute fabric.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Sends machine health JSON response.
        """
        executor: ShellCommandExecutor = ShellCommandExecutor(
            workspace_dir=self.server.session_engine._workspace_dir
        )
        hosts: list[str] = executor.get_available_hosts()
        monitor: RemoteHostMonitor = RemoteHostMonitor()

        import asyncio

        loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            machines_data: list[dict[str, Any]] = loop.run_until_complete(
                monitor.query_all_hosts(hosts=hosts, timeout_seconds=4.0)
            )
        except Exception:
            machines_data = []
        finally:
            try:
                loop.close()
            except Exception:
                pass

        self._send_json_response({"machines": machines_data})

    def _handle_get_introspect(self) -> None:
        """Return runtime introspection metadata for commands, harnesses, schemas.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Sends introspection JSON response.
        """
        intro: NeuriIntrospector = self.server.introspector
        se: NeuriSessionEngine = self.server.session_engine

        commands = intro.discover_slash_commands(se._slash_router)
        harnesses_info = intro.discover_harnesses_and_models(se)
        schemas = intro.export_pydantic_schemas()

        self._send_json_response({
            "slash_commands": commands,
            "harnesses_info": harnesses_info,
            "schemas": schemas,
        })

    def _handle_get_volumes(self) -> None:
        """Discover neuroimaging volume and surface files in current workspace.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Sends list of discovered volume records as JSON.
        """
        ws: Path = self.server.session_engine._workspace_dir
        explorer: LocalFileExplorer = LocalFileExplorer()
        found: list[dict[str, Any]] = []

        # 1. Registered artifacts from blackboard
        with contextlib.suppress(Exception):
            bb_artifacts = (
                self.server.session_engine._blackboard.list_artifacts()
            )
            for art in bb_artifacts:
                name: str = Path(art.posix_path).name
                if explorer.is_volume_file(name):
                    found.append({
                        "name": name,
                        "rel_path": art.posix_path,
                        "abs_path": art.posix_path,
                        "host": art.host,
                        "size_str": explorer.format_file_size(art.size_bytes),
                        "uri": art.uri,
                    })

        # 2. Workspace directory scan
        try:
            for p in ws.rglob("*"):
                if any(part.startswith(".") for part in p.parts):
                    continue
                if p.is_file() and explorer.is_volume_file(p.name):
                    rel_p: str = str(p.relative_to(ws))
                    if not any(f["abs_path"] == str(p) for f in found):
                        found.append({
                            "name": p.name,
                            "rel_path": rel_p,
                            "abs_path": str(p),
                            "host": "localhost",
                            "size_str": explorer.format_file_size(
                                p.stat().st_size
                            ),
                            "uri": f"file://{p}",
                        })
        except Exception:
            pass

        self._send_json_response({"volumes": found[:150]})

    def _handle_post_input(self) -> None:
        """Process user research prompt or slash command.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Dispatches input and sends resulting turn.
        """
        payload: dict[str, Any] = self._read_json_payload()
        text: str = str(payload.get("text", "")).strip()
        if not text:
            self._send_json_response({"error": "Empty input"}, status=400)
            return

        # Record in history
        self.server.history_manager.add_entry(text)

        # Run via session engine
        import asyncio

        loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            turn: ChatTurn = loop.run_until_complete(
                self.server.session_engine.submit_user_input(text)
            )
        except Exception as exc:
            self._send_json_response({
                "turn_id": f"err_{uuid.uuid4().hex[:8]}",
                "role": "assistant",
                "content": f"⚠️ **Execution Error**: {exc}",
                "thinking_trace": None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return
        finally:
            try:
                loop.close()
            except Exception:
                pass

        self._send_json_response({
            "turn_id": turn.turn_id,
            "role": turn.role.value,
            "content": turn.content,
            "thinking_trace": turn.thinking_trace,
            "timestamp": turn.timestamp.isoformat(),
        })

    def _handle_post_shell(self) -> None:
        """Execute local or remote shell command.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Dispatches shell command and sends result card.
        """
        payload: dict[str, Any] = self._read_json_payload()
        command: str = str(payload.get("command", "")).strip()
        host: str = str(payload.get("host", "localhost")).strip()

        if not command:
            self._send_json_response({"error": "Empty command"}, status=400)
            return

        import asyncio

        loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            turn: ChatTurn = loop.run_until_complete(
                self.server.session_engine.execute_shell_command(command, host)
            )
        except Exception as exc:
            self._send_json_response({
                "turn_id": f"err_{uuid.uuid4().hex[:8]}",
                "role": "assistant",
                "content": f"⚠️ **Shell Error**: {exc}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return
        finally:
            try:
                loop.close()
            except Exception:
                pass

        self._send_json_response({
            "turn_id": turn.turn_id,
            "role": turn.role.value,
            "content": turn.content,
            "timestamp": turn.timestamp.isoformat(),
        })

    def _handle_post_theme(self) -> None:
        """Change active visual color theme.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Persists theme and emits SSE notification.
        """
        payload: dict[str, Any] = self._read_json_payload()
        theme_name: str = str(payload.get("theme", "")).strip()
        if not theme_name:
            self._send_json_response({"error": "No theme specified"}, status=400)
            return

        success: bool = self.server.theme_manager.set_active_theme(theme_name)
        if success:
            updated_theme: NeuriTheme = self.server.theme_manager.get_theme(
                theme_name, fallback_to_default=True
            ) or self.server.theme_manager.get_default_theme()

            # Broadcast theme update to SSE clients
            self.server.session_engine.emit_event(
                event_type=SessionEventType.STATUS_UPDATE,
                payload={"action": "change_theme", "theme": updated_theme.to_dict()},
            )
            self._send_json_response({
                "success": True,
                "theme": updated_theme.to_dict(),
            })
        else:
            self._send_json_response(
                {"error": f"Failed to activate theme '{theme_name}'"}, status=400
            )

    def _handle_post_dag_node(self) -> None:
        """Update node task instruction, harness, or model in active workflow.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Updates blackboard and returns status.
        """
        payload: dict[str, Any] = self._read_json_payload()
        if payload.get("action") == "create" or (
            not payload.get("node_id") and payload.get("instruction")
        ):
            self._handle_post_dag_node_new(payload)
            return

        node_id: str = str(payload.get("node_id", "")).strip()
        new_instruction: str | None = payload.get("instruction")
        new_harness: str | None = payload.get("harness_id")
        new_model: str | None = payload.get("model")

        if not node_id:
            self._send_json_response({"error": "Missing node_id"}, status=400)
            return

        bb: Blackboard = self.server.session_engine._blackboard
        node: TaskNode | None = bb.get_node(node_id)
        if not node:
            self._send_json_response(
                {"error": f"Node '{node_id}' not found"}, status=404
            )
            return

        if new_instruction is not None and node.envelope:
            node.envelope.task_instruction = new_instruction.strip()
            bb.update_node_envelope(node_id, node.envelope)

        if new_harness is not None:
            node.harness_id = new_harness.strip()
            with bb.connection() as conn:
                conn.execute(
                    "UPDATE task_nodes SET harness_id = ? WHERE node_id = ?",
                    (new_harness.strip(), node_id),
                )
            if node.envelope:
                node.envelope.harness_id = new_harness.strip()
                if new_model is not None:
                    node.envelope.model = new_model.strip()
                bb.update_node_envelope(node_id, node.envelope)

        self._send_json_response({"success": True, "node_id": node_id})

    def _handle_post_dag_node_new(
        self, payload_dict: dict[str, Any] | None = None
    ) -> None:
        """Create and add a new task node and optional dependency edge to DAG.

        Parameters
        ------------
        payload_dict: dict[str, Any] | None
            Optional pre-parsed payload dictionary. Defaults to None.

        Returns
        --------
            None: NoneType object
                Creates node in blackboard and sends JSON response.
        """
        payload: dict[str, Any] = (
            payload_dict
            if payload_dict is not None
            else self._read_json_payload()
        )
        instruction: str = str(
            payload.get("instruction", "Execute research step")
        ).strip()
        role: str = str(
            payload.get("agent_role", "neuroimaging_specialist")
        ).strip()
        harness: str = str(payload.get("harness_id", "agy")).strip()
        model_name: str | None = payload.get("model")
        parent_id: str | None = payload.get("parent_node_id")

        se: NeuriSessionEngine = self.server.session_engine
        wf_id: str | None = se.current_workflow_id
        if not wf_id and hasattr(se, "_slash_router"):
            wf_id = getattr(
                se._slash_router, "_last_planned_workflow_id", None
            )
        if not wf_id:
            wf_dicts = se._blackboard.list_workflows()
            if wf_dicts:
                wf_id = str(wf_dicts[-1].get("workflow_id", ""))
        if not wf_id:
            wf_id = f"wf_{uuid.uuid4().hex[:12]}"
            se._blackboard.create_workflow(
                workflow_id=wf_id,
                prompt=instruction,
            )
            se._current_workflow_id = wf_id
            if hasattr(se, "_slash_router"):
                se._slash_router._last_planned_workflow_id = wf_id

        existing_nodes: list[TaskNode] = se._blackboard.get_nodes_by_workflow(
            wf_id
        )
        step_num: int = len(existing_nodes) + 1
        clean_role: str = role.replace("-", "_")
        node_id: str = f"node_{wf_id}_{step_num}_{clean_role}"

        envelope: NeuriTaskEnvelope = NeuriTaskEnvelope(
            workflow_id=wf_id,
            node_id=node_id,
            agent_role=role,
            harness_id=harness,
            model=model_name,
            task_instruction=instruction,
            execution_mode="headless_json",
        )
        node: TaskNode = TaskNode(
            node_id=node_id,
            workflow_id=wf_id,
            agent_role=role,
            harness_id=harness,
            model=model_name,
            state=TaskState.PENDING,
            attempt=0,
            max_retries=3,
            envelope=envelope,
        )
        se._blackboard.create_node(node)

        # Wire dependency edge if parent specified
        if parent_id and parent_id != "none":
            if parent_id == "auto" and existing_nodes:
                parent_id = existing_nodes[-1].node_id
            if parent_id in {n.node_id for n in existing_nodes}:
                edge: TaskEdge = TaskEdge(
                    workflow_id=wf_id,
                    parent_node_id=parent_id,
                    child_node_id=node_id,
                )
                se._blackboard.add_edge(edge)

        self._send_json_response({
            "success": True,
            "node_id": node_id,
            "workflow_id": wf_id,
        })

    def _handle_post_history_clear(self) -> None:
        """Clear prompt and command history file.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Clears history and sends response.
        """
        self.server.history_manager.clear()
        self._send_json_response({"success": True})


__all__: list[str] = [
    "NeuriGUIHandler",
    "NeuriGUIServer",
]
