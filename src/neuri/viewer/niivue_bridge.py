"""Local HTTP bridge and scene controller for NiiVue WebGL2 visualization.

Provides an embedded HTTP server running at http://localhost:8421 that serves
the NiiVue SPA, manages declarative NiiVueSceneSpec state, and proxies
byte-range volume requests from remote spokes.
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import re
import threading
from typing import Any
from urllib.parse import parse_qs, urlparse

from neuri.core.schemas import NiiVueSceneSpec


class NiiVueBridgeHandler(BaseHTTPRequestHandler):
    """HTTP handler serving NiiVue SPA and declarative scene API endpoints.

    Parameters
    ------------
    request: Any
        Underlying socket connection request.
    client_address: tuple[str, int]
        Tuple of client IP address and port.
    server: HTTPServer
        Parent HTTP server instance.

    Returns
    --------
        NiiVueBridgeHandler: NiiVueBridgeHandler instance
            Constructed handler instance.
    """

    server_version: str = "NeuriNiiVueBridge/0.1"

    def handle_get(self) -> None:
        """Handle incoming GET requests for SPA, scene status, or file data.

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
            self._serve_static_index()
        elif path == "/api/scene":
            self._serve_scene_spec()
        elif path == "/api/file":
            query_params = parse_qs(parsed_url.query)
            uri_list = query_params.get("uri", [])
            target_uri: str = uri_list[0] if uri_list else ""
            self._serve_file_stream(target_uri)
        else:
            self.send_error(404, "Not Found")

    def handle_post(self) -> None:
        """Handle incoming POST requests to update active scene specification.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Processes JSON payload and sends HTTP response.
        """
        parsed_url = urlparse(self.path)
        if parsed_url.path == "/api/scene":
            try:
                content_len: int = int(self.headers.get("Content-Length", 0))
                body: bytes = self.rfile.read(content_len)
                payload: dict[str, Any] = json.loads(body.decode("utf-8"))
                scene_spec: NiiVueSceneSpec = NiiVueSceneSpec.model_validate(
                    payload
                )
                setattr(self.server, "active_scene", scene_spec)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
            except Exception as err:
                self.send_error(400, f"Invalid scene specification: {err}")
        else:
            self.send_error(404, "Not Found")

    do_GET = handle_get
    do_POST = handle_post

    def _serve_static_index(self) -> None:
        """Serve the local static index.html NiiVue application.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Sends HTML file response.
        """
        index_file: Path = (
            Path(__file__).resolve().parent / "static" / "index.html"
        )
        if not index_file.is_file():
            self.send_error(404, "Static index.html template not found")
            return

        content: bytes = index_file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _serve_scene_spec(self) -> None:
        """Return the currently active declarative scene specification as JSON.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Sends JSON scene response.
        """
        scene: NiiVueSceneSpec | None = getattr(
            self.server, "active_scene", None
        )
        if scene is None:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"{}")
            return

        payload_bytes: bytes = json.dumps(scene.model_dump()).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload_bytes)))
        self.end_headers()
        self.wfile.write(payload_bytes)

    def _serve_file_stream(self, uri: str) -> None:
        """Stream local or proxied neuroimaging volume bytes with Range support.

        Parameters
        ------------
        uri: str
            Raw URI or local file path string.

        Returns
        --------
            None: NoneType object
                Sends binary stream with Range support.
        """
        # Strip file:// prefix if present
        clean_path_str: str = uri
        if clean_path_str.startswith("file://"):
            clean_path_str = clean_path_str[7:]

        local_file: Path = Path(clean_path_str)
        if not local_file.is_file():
            self.send_error(404, f"File not found: {uri}")
            return

        try:
            total_size: int = local_file.stat().st_size
        except OSError:
            self.send_error(500, "Unable to stat file")
            return

        mime_type: str = "application/octet-stream"
        if local_file.name.lower().endswith(".gz"):
            mime_type = "application/gzip"

        range_hdr: str | None = self.headers.get("Range")
        if range_hdr:
            match = re.match(r"^bytes=(\d*)-(\d*)$", range_hdr.strip())
            if not match:
                self.send_response(416, "Range Not Satisfiable")
                self.send_header("Content-Range", f"bytes */{total_size}")
                self.end_headers()
                return

            s_str, e_str = match.groups()
            start: int = int(s_str) if s_str else 0
            end: int = min(int(e_str), total_size - 1) if e_str else total_size - 1
            length: int = end - start + 1

            self.send_response(206, "Partial Content")
            self.send_header("Content-Type", mime_type)
            self.send_header(
                "Content-Range", f"bytes {start}-{end}/{total_size}"
            )
            self.send_header("Content-Length", str(length))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()

            with local_file.open("rb") as f:
                f.seek(start)
                left: int = length
                while left > 0:
                    chunk: bytes = f.read(min(65536, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        else:
            self.send_response(200, "OK")
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(total_size))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()

            with local_file.open("rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress standard logging to stderr.

        Parameters
        ------------
        format: str
            Log format string.
        *args: Any
            Log arguments.

        Returns
        --------
            None: NoneType object
                No-op suppression.
        """
        pass


class NiiVueBridge:
    """Local server and state bridge for NiiVue WebGL2 visualization.

    Parameters
    ------------
    host: str
        Binding host address. Defaults to '127.0.0.1'.
    port: int
        Binding port number. Defaults to 8421.

    Returns
    --------
        NiiVueBridge: NiiVueBridge instance
            Constructed bridge controller.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8421) -> None:
        """Initialize NiiVue bridge configuration.

        Parameters
        ------------
        host: str
            Binding host address. Defaults to '127.0.0.1'.
        port: int
            Binding port number. Defaults to 8421.

        Returns
        --------
            None: NoneType object
                Initializes bridge controller state.
        """
        self._host: str = host
        self._port: int = port
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._is_running: bool = False
        self._active_scene: NiiVueSceneSpec | None = None

    def start(self) -> None:
        """Start the NiiVue bridge server in a background thread.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Spawns server thread.
        """
        if self._is_running:
            return

        server = HTTPServer((self._host, self._port), NiiVueBridgeHandler)
        setattr(server, "active_scene", self._active_scene)
        self._server = server
        self._port = server.server_address[1]
        self._is_running = True

        thread = threading.Thread(
            target=self._server.serve_forever, daemon=True
        )
        self._thread = thread
        thread.start()

    def stop(self) -> None:
        """Stop the NiiVue bridge server.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Shuts down server instance.
        """
        if not self._is_running or self._server is None:
            return

        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._is_running = False

    def is_running(self) -> bool:
        """Check whether the bridge server is currently running.

        Parameters
        ------------
        None

        Returns
        --------
            bool: boolean object
                True if bridge is active.
        """
        return self._is_running

    def get_url(self) -> str:
        """Retrieve the canonical browser URL for the active session.

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                URL string, e.g. 'http://127.0.0.1:8421'.
        """
        url_str: str = f"http://{self._host}:{self._port}"
        return url_str

    def push_scene(self, scene: NiiVueSceneSpec) -> bool:
        """Update the active scene manifest rendered in connected visualizers.

        Parameters
        ------------
        scene: NiiVueSceneSpec
            Declarative scene specification model.

        Returns
        --------
            bool: boolean object
                True if scene was updated successfully.
        """
        self._active_scene = scene
        if self._server is not None:
            setattr(self._server, "active_scene", scene)
        return True

    def get_scene(self) -> NiiVueSceneSpec | None:
        """Retrieve the currently active scene specification.

        Parameters
        ------------
        None

        Returns
        --------
            NiiVueSceneSpec | None: NiiVueSceneSpec or None
                Current scene spec, or None if no scene has been pushed.
        """
        return self._active_scene


__all__: list[str] = [
    "NiiVueBridge",
    "NiiVueBridgeHandler",
]
