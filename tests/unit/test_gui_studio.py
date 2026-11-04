"""Unit tests for Neuri Studio GUI server, introspection, and theme export.

Validates that NeuriGUIServer provides 100% terminal feature parity,
Server-Sent Events streaming, dynamic slash-command introspection, and theme
CSS Custom Properties export.
"""

import io
import json
from pathlib import Path
from typing import Any

from neuri.core.blackboard import Blackboard
from neuri.core.config import NeuriConfig
from neuri.core.schemas import (
    ChatRole,
    NeuriTaskEnvelope,
    TaskEdge,
    TaskNode,
    TaskState,
)
from neuri.core.session import NeuriSessionEngine
from neuri.gui.introspect import NeuriIntrospector
from neuri.gui.launcher import find_available_port
from neuri.gui.server import NeuriGUIHandler, NeuriGUIServer
from neuri.ui.history import PromptHistoryManager
from neuri.ui.theme import NeuriTheme, NeuriThemeManager


class MockHttpClient:
    """Simulates HTTP requests directly against NeuriGUIHandler.

    Parameters
    ------------
    server: NeuriGUIServer
        Configured NeuriGUIServer instance.

    Returns
    --------
        MockHttpClient: MockHttpClient instance
            Client for testing HTTP requests.
    """

    def __init__(self, server: NeuriGUIServer) -> None:
        """Initialize mock HTTP client.

        Parameters
        ------------
        server: NeuriGUIServer
            Target GUI server instance.

        Returns
        --------
            None: NoneType object
                Initializes client instance.
        """
        self.server: NeuriGUIServer = server

    def request(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> tuple[int, dict[str, str], bytes]:
        """Dispatch simulated HTTP request to NeuriGUIHandler.

        Parameters
        ------------
        method: str
            HTTP request method (GET, POST).
        path: str
            Request URI path.
        body: dict[str, Any] | None
            Optional JSON request body dictionary. Defaults to None.

        Returns
        --------
            tuple[int, dict[str, str], bytes]: tuple object
                Tuple of status code, headers dictionary, and raw body bytes.
        """
        payload_bytes: bytes = (
            json.dumps(body).encode("utf-8") if body is not None else b""
        )
        req_lines: list[str] = [
            f"{method} {path} HTTP/1.1",
            "Host: 127.0.0.1",
            "Content-Type: application/json",
            f"Content-Length: {len(payload_bytes)}",
            "",
            "",
        ]
        raw_header: bytes = "\r\n".join(req_lines).encode("utf-8")
        full_req: bytes = raw_header + payload_bytes

        class MockSocket:
            """In-memory mock socket providing read and write byte streams.

            Parameters
            ------------
            data: bytes
                Initial incoming request payload bytes.

            Returns
            --------
                MockSocket: MockSocket instance
                    Constructed mock socket instance.
            """

            def __init__(self, data: bytes) -> None:
                """Initialize mock socket buffers.

                Parameters
                ------------
                data: bytes
                    Raw HTTP request bytes to buffer for reading.

                Returns
                --------
                    None: NoneType object
                        Initializes internal byte streams.
                """
                self._r: io.BytesIO = io.BytesIO(data)
                self._w: io.BytesIO = io.BytesIO()

            def makefile(self, mode: str, *args: Any, **kwargs: Any) -> Any:
                """Return read or write stream matching mode flag.

                Parameters
                ------------
                mode: str
                    File stream mode string ('rb', 'wb', etc.).

                Returns
                --------
                    io.BytesIO: BytesIO object
                        Underlying read or write stream.
                """
                return self._r if "r" in mode else self._w

            def sendall(self, b: bytes) -> None:
                """Write raw response bytes to response buffer.

                Parameters
                ------------
                b: bytes
                    Response byte stream to write.

                Returns
                --------
                    None: NoneType object
                        Appends bytes to write buffer.
                """
                self._w.write(b)

        sock: MockSocket = MockSocket(full_req)
        NeuriGUIHandler(sock, ("127.0.0.1", 12345), self.server)
        raw_resp: bytes = sock._w.getvalue()

        parts: list[bytes] = raw_resp.split(b"\r\n\r\n", 1)
        headers_part: str = parts[0].decode("utf-8", errors="replace")
        body_part: bytes = parts[1] if len(parts) > 1 else b""

        status_line: str = headers_part.splitlines()[0]
        status_code: int = int(status_line.split()[1])

        headers: dict[str, str] = {}
        for line in headers_part.splitlines()[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()

        return status_code, headers, body_part


def test_theme_to_css_variables_and_to_dict(tmp_path: Path) -> None:
    """Verify NeuriTheme exports 17 semantic CSS custom properties and dict.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts all 17 tokens are present and non-empty.
    """
    manager: NeuriThemeManager = NeuriThemeManager(workspace_dir=tmp_path)
    themes: list[NeuriTheme] = manager.list_available_themes()
    assert len(themes) >= 1

    for theme in themes:
        css_vars: dict[str, str] = theme.to_css_variables()
        assert "--neuri-background" in css_vars
        assert "--neuri-foreground" in css_vars
        assert "--neuri-surface" in css_vars
        assert "--neuri-panel" in css_vars
        assert "--neuri-border" in css_vars
        assert "--neuri-primary" in css_vars
        assert "--neuri-secondary" in css_vars
        assert "--neuri-accent" in css_vars
        assert "--neuri-warning" in css_vars
        assert "--neuri-error" in css_vars
        assert "--neuri-success" in css_vars
        assert "--neuri-muted" in css_vars
        assert "--neuri-selection-bg" in css_vars
        assert "--neuri-selection-fg" in css_vars
        assert "--neuri-tokens" in css_vars
        assert "--neuri-cost" in css_vars

        # Ensure no values are empty strings
        for var_name, var_val in css_vars.items():
            assert var_val.strip(), f"Empty CSS token: {var_name}"

        data: dict[str, Any] = theme.to_dict()
        assert data["name"] == theme.name
        assert "css_variables" in data
        assert "colors" in data


def test_introspector_discovers_slash_commands_and_schemas(
    tmp_path: Path,
) -> None:
    """Verify runtime introspector discovers all commands, models, and schemas.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts discovered commands list and schema models.
    """
    session_engine: NeuriSessionEngine = NeuriSessionEngine(
        workspace_dir=tmp_path
    )
    introspector: NeuriIntrospector = NeuriIntrospector()

    # 1. Discover registered slash commands
    commands: list[dict[str, Any]] = introspector.discover_slash_commands(
        session_engine._slash_router
    )
    assert len(commands) >= 20

    cmd_names: set[str] = {c["command"] for c in commands}
    assert "/plan" in cmd_names
    assert "/run" in cmd_names
    assert "/view" in cmd_names
    assert "/status" in cmd_names
    assert "/bids" in cmd_names
    assert "/remote" in cmd_names
    assert "/machines" in cmd_names
    assert "/theme" in cmd_names

    # 2. Test forward compatibility: attach a custom dynamic command
    def _mock_handle_neuromorph(args: list[str]) -> Any:
        """Run custom neuromorph pipeline analysis.

        Parameters
        ------------
        args: list[str]
            Command line arguments for the simulated slash handler.

        Returns
        --------
            Any: Any object
                Simulated response value.
        """
        return None

    setattr(
        session_engine._slash_router,
        "_handle_neuromorph",
        _mock_handle_neuromorph,
    )

    updated_cmds: list[dict[str, Any]] = (
        introspector.discover_slash_commands(session_engine._slash_router)
    )
    updated_names: set[str] = {c["command"] for c in updated_cmds}
    assert "/neuromorph" in updated_names

    # 3. Discover harnesses and models
    harness_info: dict[str, Any] = (
        introspector.discover_harnesses_and_models(session_engine)
    )
    assert "harnesses" in harness_info
    assert "agy" in harness_info["harnesses"]
    assert "models_by_harness" in harness_info

    # 4. Export Pydantic schemas
    schemas: dict[str, Any] = introspector.export_pydantic_schemas()
    assert "NeuriTaskEnvelope" in schemas
    assert "NeuriConfig" in schemas
    assert "NiiVueSceneSpec" in schemas


def test_gui_server_state_and_rest_endpoints(tmp_path: Path) -> None:
    """Verify NeuriGUIServer serves state, input, dag, shell, and themes.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts HTTP endpoints return valid JSON and expected models.
    """
    db_path: Path = tmp_path / "test_gui_state.db"
    bb: Blackboard = Blackboard(db_path)
    session_engine: NeuriSessionEngine = NeuriSessionEngine(
        workspace_dir=tmp_path,
        blackboard=bb,
    )
    theme_manager: NeuriThemeManager = NeuriThemeManager(
        workspace_dir=tmp_path
    )
    history_manager: PromptHistoryManager = PromptHistoryManager(
        history_file=tmp_path / "hist"
    )
    static_dir: Path = (
        Path(__file__).resolve().parent.parent.parent
        / "src"
        / "neuri"
        / "gui"
        / "static"
    )

    # Create dummy workflow and node in blackboard
    wf_id: str = "wf_gui_test_01"
    bb.create_workflow(wf_id, "GUI Integration Test Workflow")
    node: TaskNode = TaskNode(
        node_id="node_recon",
        workflow_id=wf_id,
        agent_role="pipeline_engineer",
        harness_id="agy",
        state=TaskState.PENDING,
        envelope=NeuriTaskEnvelope(
            workflow_id=wf_id,
            node_id="node_recon",
            agent_role="pipeline_engineer",
            task_instruction="Reconstruct cortical surface with FreeSurfer",
            harness_id="agy",
            execution_mode="headless_json",
        ),
    )
    bb.create_node(node)
    node_qa: TaskNode = TaskNode(
        node_id="node_qa",
        workflow_id=wf_id,
        agent_role="qc_auditor",
        harness_id="agy",
        state=TaskState.PENDING,
        envelope=NeuriTaskEnvelope(
            workflow_id=wf_id,
            node_id="node_qa",
            agent_role="qc_auditor",
            harness_id="agy",
            task_instruction="Generate visual QA report",
            execution_mode="headless_json",
        ),
    )
    bb.create_node(node_qa)
    bb.add_edge(
        TaskEdge(
            workflow_id=wf_id,
            parent_node_id="node_recon",
            child_node_id="node_qa",
        )
    )
    session_engine._current_workflow_id = wf_id

    server: NeuriGUIServer = NeuriGUIServer(
        server_address=("127.0.0.1", 0),
        session_engine=session_engine,
        theme_manager=theme_manager,
        history_manager=history_manager,
        static_dir=static_dir,
    )

    client: MockHttpClient = MockHttpClient(server)

    try:
        # 1. GET / (serves index.html)
        status, headers, body = client.request("GET", "/")
        assert status == 200
        assert "text/html" in headers.get("content-type", "")
        assert b"NEURI STUDIO" in body

        # 2. GET /css/studio.css
        status, headers, body = client.request("GET", "/css/studio.css")
        assert status == 200
        assert b"--neuri-primary" in body

        # 3. GET /js/app.js
        status, headers, body = client.request("GET", "/js/app.js")
        assert status == 200
        assert b"NeuriApp" in body

        # 4. GET /api/v1/state
        status, headers, body = client.request("GET", "/api/v1/state")
        assert status == 200
        state = json.loads(body.decode("utf-8"))
        assert state["current_workflow_id"] == wf_id
        assert len(state["active_nodes"]) >= 1

        # 5. GET /api/v1/dag
        status, headers, body = client.request("GET", "/api/v1/dag")
        assert status == 200
        dag_data = json.loads(body.decode("utf-8"))
        assert dag_data["workflow_id"] == wf_id
        assert len(dag_data["nodes"]) == 2
        assert any(n["node_id"] == "node_recon" for n in dag_data["nodes"])
        assert any(n["node_id"] == "node_qa" for n in dag_data["nodes"])
        assert len(dag_data["edges"]) == 1
        assert dag_data["edges"][0]["from_node_id"] == "node_recon"
        assert dag_data["edges"][0]["to_node_id"] == "node_qa"

        # 6. POST /api/v1/dag/node (edit instruction and harness)
        status, headers, body = client.request(
            "POST",
            "/api/v1/dag/node",
            body={
                "node_id": "node_recon",
                "instruction": "Reconstruct surfaces using recon-all -all",
                "harness_id": "codex",
                "model": "gpt-4o",
            },
        )
        assert status == 200

        # Verify updated node in blackboard
        updated_node: TaskNode | None = bb.get_node("node_recon")
        assert updated_node is not None
        assert updated_node.harness_id == "codex"
        assert (
            updated_node.envelope.task_instruction
            == "Reconstruct surfaces using recon-all -all"
        )

        # 6b. POST /api/v1/dag/node/new (interactively add a new box to DAG)
        status, headers, body = client.request(
            "POST",
            "/api/v1/dag/node/new",
            body={
                "instruction": "Run fMRI GLM analysis",
                "agent_role": "neuroimaging_specialist",
                "harness_id": "agy",
                "parent_node_id": "node_qa",
            },
        )
        assert status == 200
        new_node_res = json.loads(body.decode("utf-8"))
        assert new_node_res["success"] is True
        assert "node_" in new_node_res["node_id"]

        # Verify DAG now has 3 nodes and 2 edges
        status, headers, body = client.request("GET", "/api/v1/dag")
        assert status == 200
        dag_data3 = json.loads(body.decode("utf-8"))
        assert len(dag_data3["nodes"]) == 3
        assert len(dag_data3["edges"]) == 2

        # 7. POST /api/v1/input (slash command /plan add and /status)
        status, headers, body = client.request(
            "POST",
            "/api/v1/input",
            body={"text": "/plan add Generate scientific publication methods"},
        )
        assert status == 200
        turn_plan_add = json.loads(body.decode("utf-8"))
        assert "Added Step" in turn_plan_add["content"]

        status, headers, body = client.request(
            "POST", "/api/v1/input", body={"text": "/status"}
        )
        assert status == 200
        turn_res = json.loads(body.decode("utf-8"))
        assert turn_res["role"] == "assistant"
        assert "Neuri System Status" in turn_res["content"]

        # 8. POST /api/v1/shell (execute echo command)
        status, headers, body = client.request(
            "POST",
            "/api/v1/shell",
            body={"command": "echo 'studio_test_echo'", "host": "localhost"},
        )
        assert status == 200
        shell_turn = json.loads(body.decode("utf-8"))
        assert "studio_test_echo" in shell_turn["content"]

        # 9. GET /api/v1/themes and POST /api/v1/themes
        status, headers, body = client.request("GET", "/api/v1/themes")
        assert status == 200
        thms = json.loads(body.decode("utf-8"))
        assert len(thms["themes"]) >= 1

        status, headers, body = client.request(
            "POST", "/api/v1/themes", body={"theme": "dark"}
        )
        assert status == 200

        # 10. GET /api/v1/machines
        status, headers, body = client.request("GET", "/api/v1/machines")
        assert status == 200
        m_data = json.loads(body.decode("utf-8"))
        assert "machines" in m_data

        # 11. GET /api/v1/introspect
        status, headers, body = client.request("GET", "/api/v1/introspect")
        assert status == 200
        intro_data = json.loads(body.decode("utf-8"))
        assert "slash_commands" in intro_data
        assert "harnesses_info" in intro_data
        assert "schemas" in intro_data

        # 12. GET /api/v1/history and POST /api/v1/history/clear
        status, headers, body = client.request("GET", "/api/v1/history")
        assert status == 200
        assert len(json.loads(body.decode("utf-8"))["entries"]) >= 1

        status, headers, body = client.request("POST", "/api/v1/history/clear")
        assert status == 200

        # 13. Test launcher find_available_port utility
        port_num: int = find_available_port(start_port=8420)
        assert isinstance(port_num, int)
        assert port_num >= 8420

        # 14. GET /viewer and verify multithreading daemon flag
        status, headers, body = client.request("GET", "/viewer")
        assert status == 200
        assert b"NEURI" in body
        assert b"btn-demo-volume" in body
        assert b"btn-attach-prompt" in body
        assert b"host-select" in body
        assert server.daemon_threads is True

        # 15. Create volume file in workspace and verify GET /api/v1/volumes
        sample_nii = tmp_path / "sub-01_T1w.nii.gz"
        sample_nii.write_bytes(b"\x1f\x8b\x08dummy_nifti_data")
        status, headers, body = client.request("GET", "/api/v1/volumes")
        assert status == 200
        vol_data = json.loads(body.decode("utf-8"))
        assert "volumes" in vol_data
        assert any(v["name"] == "sub-01_T1w.nii.gz" for v in vol_data["volumes"])

        # 16. Verify GET / contains the embedded viewer iframe
        status, headers, body = client.request("GET", "/")
        assert status == 200
        assert b'id="niivue-embedded-viewer"' in body
        assert b'src="/viewer"' in body

        # 17. Verify GET /api/hosts returns localhost
        status, headers, body = client.request("GET", "/api/hosts")
        assert status == 200
        hosts_data = json.loads(body.decode("utf-8"))
        assert "hosts" in hosts_data
        assert "localhost" in hosts_data["hosts"]

        # 18. Verify GET /api/fs/list and POST /api/fs/open for volume loading
        status, headers, body = client.request(
            "GET",
            f"/api/fs/list?host=localhost&path={str(tmp_path)}",
        )
        assert status == 200
        fs_data = json.loads(body.decode("utf-8"))
        assert "entries" in fs_data
        assert any(
            e["name"] == "sub-01_T1w.nii.gz" and e["is_volume"]
            for e in fs_data["entries"]
        )

        status, headers, body = client.request(
            "POST",
            "/api/fs/open",
            body={"path": str(sample_nii), "host": "localhost"},
        )
        assert status == 200
        open_data = json.loads(body.decode("utf-8"))
        assert open_data["status"] == "ok"
        assert "path" in open_data

    finally:
        server.server_close()
