"""Local HTTP bridge and scene controller for NiiVue WebGL2 visualization.

Provides an embedded HTTP server running at http://localhost:8421 that serves
the NiiVue SPA, manages declarative NiiVueSceneSpec state, lists local and
remote SSH directories, and proxies byte-range volume requests.
"""

import json
import os
import re
import tempfile
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from neuri.core.schemas import NiiVueLayerSpec, NiiVueSceneSpec
from neuri.viewer.local_explorer import LocalFileExplorer


class NiiVueHTTPServer(HTTPServer):
    """HTTP server carrying active scene state for NiiVue bridge.

    Parameters
    ------------
    server_address: tuple[str, int]
        Host IP and port tuple.
    RequestHandlerClass: type[BaseHTTPRequestHandler]
        Handler class constructing per-request responses.

    Returns
    --------
        NiiVueHTTPServer: NiiVueHTTPServer instance
            Server instance with typed scene attribute.
    """

    active_scene: NiiVueSceneSpec | None = None
    latest_selection: dict[str, Any] | None = None


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
    server: NiiVueHTTPServer

    def handle_get(self) -> None:
        """Handle incoming GET requests for SPA, scene, hosts, or file data.

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
        elif path == "/api/scene/selection":
            self._serve_selection()
        elif path == "/api/hosts":
            self._serve_hosts()
        elif path.startswith("/api/file"):
            query_params = parse_qs(parsed_url.query)
            uri_list = query_params.get("uri", [])
            target_uri: str = uri_list[0] if uri_list else ""
            if not target_uri and len(path) > len("/api/file/"):
                target_uri = path[len("/api/file/") :]
            self._serve_file_stream(target_uri)
        elif path == "/api/fs/list":
            query_params = parse_qs(parsed_url.query)
            path_list = query_params.get("path", [])
            host_list = query_params.get("host", [])
            req_path: str | None = path_list[0] if path_list else None
            req_host: str = host_list[0] if host_list else "localhost"
            self._serve_fs_list(req_path, req_host)
        elif path == "/api/neurosynth":
            query_params = parse_qs(parsed_url.query)
            x_val = query_params.get("x", ["0.0"])[0]
            y_val = query_params.get("y", ["0.0"])[0]
            z_val = query_params.get("z", ["0.0"])[0]
            radius_val = query_params.get("radius", ["6"])[0]
            top_val = query_params.get("top", ["10"])[0]
            self._serve_neurosynth(x_val, y_val, z_val, radius_val, top_val)
        elif path == "/api/fsl-atlas":
            query_params = parse_qs(parsed_url.query)
            x_val = query_params.get("x", ["0.0"])[0]
            y_val = query_params.get("y", ["0.0"])[0]
            z_val = query_params.get("z", ["0.0"])[0]
            min_prob_val = query_params.get("min_prob", ["5.0"])[0]
            atlas_val = query_params.get("atlas", [])
            self._serve_fsl_atlas(x_val, y_val, z_val, min_prob_val, atlas_val)
        else:
            self.send_error(404, "Not Found")

    def handle_post(self) -> None:
        """Handle incoming POST requests for scene updates or file selection.

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
            self._handle_post_scene()
        elif parsed_url.path == "/api/scene/selection":
            self._handle_post_selection()
        elif parsed_url.path == "/api/open-dialog":
            self._handle_open_dialog()
        elif parsed_url.path == "/api/fs/open":
            self._handle_fs_open()
        else:
            self.send_error(404, "Not Found")

    def _get_cors_origin(self) -> str:
        """Determine permitted CORS origin matching localhost or 127.0.0.1.

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                Permitted Origin string.
        """
        origin_hdr: str | None = self.headers.get("Origin")
        if origin_hdr and re.match(
            r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$", origin_hdr
        ):
            return origin_hdr
        return "http://127.0.0.1"

    def is_path_permitted(self, file_path: Path) -> bool:
        """Verify resolved path resides within configured allowed roots.

        Parameters
        ------------
        file_path: Path
            Resolved absolute path to verify.

        Returns
        --------
            bool: boolean object
                True if path is within an allowed root directory.
        """
        allowed: list[Path] = getattr(self.server, "allowed_roots", [])
        if not allowed:
            allowed = [
                Path.cwd(),
                Path(tempfile.gettempdir()),
                Path.home() / ".neuri",
            ]
        try:
            resolved_target: Path = file_path.resolve()
            forbidden_roots = [
                Path.home() / ".ssh",
                Path.home() / ".aws",
                Path.home() / ".gnupg",
                Path("/etc"),
            ]
            for f_root in forbidden_roots:
                try:
                    res_f = f_root.resolve()
                    if (
                        resolved_target == res_f
                        or res_f in resolved_target.parents
                    ):
                        return False
                except Exception:
                    pass
            for root in allowed:
                resolved_root: Path = root.resolve()
                if (
                    resolved_target == resolved_root
                    or resolved_root in resolved_target.parents
                ):
                    return True
        except Exception:
            return False
        return False

    def handle_options(self) -> None:
        """Handle CORS pre-flight requests from browser clients.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Sends CORS pre-flight response headers.
        """
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", self._get_cors_origin())
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Range, Content-Type, Accept, Origin",
        )
        self.end_headers()

    do_GET = handle_get
    do_POST = handle_post
    do_OPTIONS = handle_options

    def _handle_post_scene(self) -> None:
        """Handle incoming POST request to update active scene specification.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Processes JSON payload and sends HTTP response.
        """
        try:
            content_len: int = int(self.headers.get("Content-Length", 0))
            body: bytes = self.rfile.read(content_len)
            payload: dict[str, Any] = json.loads(body.decode("utf-8"))
            scene_spec: NiiVueSceneSpec = NiiVueSceneSpec.model_validate(
                payload
            )
            self.server.active_scene = scene_spec
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        except Exception as err:
            self.send_error(400, f"Invalid scene specification: {err}")

    def _handle_post_selection(self) -> None:
        """Handle incoming POST request transmitting 3D coordinate feedback.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Stores selection state and sends JSON acknowledgement.
        """
        try:
            content_len: int = int(self.headers.get("Content-Length", 0))
            body: bytes = self.rfile.read(content_len)
            payload: dict[str, Any] = json.loads(body.decode("utf-8"))
            self.server.latest_selection = payload
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", self._get_cors_origin())
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok","recorded":true}')
        except Exception as err:
            self.send_error(400, f"Invalid selection payload: {err}")

    def _serve_selection(self) -> None:
        """Return the most recently clicked 3D voxel coordinate selection.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Sends JSON response with latest coordinate and atlas label.
        """
        sel: dict[str, Any] | None = getattr(
            self.server, "latest_selection", None
        )
        payload_bytes: bytes = json.dumps(sel or {}).encode("utf-8")
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", self._get_cors_origin())
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload_bytes)))
        self.end_headers()
        self.wfile.write(payload_bytes)

    def _serve_hosts(self) -> None:
        """Serve JSON list of available local and remote SSH hosts.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Sends JSON host list response.
        """
        explorer: LocalFileExplorer = LocalFileExplorer()
        hosts_info: dict[str, Any] = explorer.get_available_hosts()
        payload_bytes: bytes = json.dumps(hosts_info).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload_bytes)))
        self.end_headers()
        self.wfile.write(payload_bytes)

    def _serve_neurosynth(
        self,
        x_str: str,
        y_str: str,
        z_str: str,
        radius_str: str = "6",
        top_str: str = "10",
    ) -> None:
        """Serve JSON decoding top functional associations from Neurosynth.

        Parameters
        ------------
        x_str: str
            MNI X coordinate string.
        y_str: str
            MNI Y coordinate string.
        z_str: str
            MNI Z coordinate string.
        radius_str: str
            Sphere radius string. Defaults to "6".
        top_str: str
            Top associations count string. Defaults to "10".

        Returns
        --------
            None: NoneType object
                Sends JSON Neurosynth lookup response.
        """
        from neuri.viewer.fsl_atlas import query_fsl_coordinates
        from neuri.viewer.neurosynth import query_neurosynth_coordinates

        try:
            x_val: float = float(x_str)
            y_val: float = float(y_str)
            z_val: float = float(z_str)
            rad_val: int = int(radius_str)
            top_val: int = int(top_str)
        except (ValueError, TypeError):
            self.send_error(400, "Invalid coordinate, radius, or top parameter.")
            return

        ns_result = query_neurosynth_coordinates(
            x=x_val, y=y_val, z=z_val, radius=rad_val, top_n=top_val
        )
        fsl_result = query_fsl_coordinates(x=x_val, y=y_val, z=z_val)

        payload_dict = ns_result.to_dict()
        payload_dict["fsl_anatomy"] = fsl_result.to_dict()

        payload_bytes: bytes = json.dumps(payload_dict).encode("utf-8")
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", self._get_cors_origin())
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload_bytes)))
        self.end_headers()
        self.wfile.write(payload_bytes)

    def _serve_fsl_atlas(
        self,
        x_str: str,
        y_str: str,
        z_str: str,
        min_prob_str: str = "5.0",
        atlas_filter: list[str] | None = None,
    ) -> None:
        """Serve JSON decoding anatomical brain regions from 20 human FSL atlases.

        Parameters
        ------------
        x_str: str
            MNI X coordinate string.
        y_str: str
            MNI Y coordinate string.
        z_str: str
            MNI Z coordinate string.
        min_prob_str: str
            Minimum probability threshold string. Defaults to "5.0".
        atlas_filter: list[str] | None
            Optional list of atlas keys. Defaults to None.

        Returns
        --------
            None: NoneType object
                Sends JSON FSL atlas lookup response.
        """
        from neuri.viewer.fsl_atlas import query_fsl_coordinates

        try:
            x_val: float = float(x_str)
            y_val: float = float(y_str)
            z_val: float = float(z_str)
            min_p: float = float(min_prob_str)
        except (ValueError, TypeError):
            self.send_error(400, "Invalid coordinate or probability parameter.")
            return

        result = query_fsl_coordinates(
            x=x_val, y=y_val, z=z_val, atlas_filter=atlas_filter, min_prob=min_p
        )
        payload_bytes: bytes = json.dumps(result.to_dict()).encode("utf-8")
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", self._get_cors_origin())
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload_bytes)))
        self.end_headers()
        self.wfile.write(payload_bytes)

    def _serve_fs_list(
        self, dir_path: str | None, host: str = "localhost"
    ) -> None:
        """Serve JSON listing of local or remote directory contents.

        Parameters
        ------------
        dir_path: str | None
            Directory path to inspect. Defaults to None.
        host: str
            Target host identifier. Defaults to 'localhost'.

        Returns
        --------
            None: NoneType object
                Sends JSON directory listing response.
        """
        if host in ("localhost", "127.0.0.1") and dir_path:
            target_dir: Path = Path(dir_path).resolve()
            if not self.is_path_permitted(target_dir):
                self.send_error(403, f"Access denied: {dir_path}")
                return

        explorer: LocalFileExplorer = LocalFileExplorer()
        listing: dict[str, Any] = explorer.list_directory(
            dir_path=dir_path, host=host
        )
        payload_bytes: bytes = json.dumps(listing).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload_bytes)))
        self.end_headers()
        self.wfile.write(payload_bytes)

    def _handle_open_dialog(self) -> None:
        """Trigger native host OS file explorer and activate selected volume.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Sends JSON response with selection outcome.
        """
        explorer: LocalFileExplorer = LocalFileExplorer()
        outcome: dict[str, Any] = explorer.pick_file_dialog()
        status: str = outcome.get("status", "canceled")
        resp_data: dict[str, Any]
        if status == "ok":
            selected_path: str = outcome["path"]
            scene: NiiVueSceneSpec = self._create_scene_for_path(selected_path)
            self.server.active_scene = scene
            resp_data = {
                "status": "ok",
                "host": "localhost",
                "path": selected_path,
                "title": Path(selected_path).name,
                "scene": scene.model_dump(),
            }
        else:
            resp_data = outcome

        payload_bytes: bytes = json.dumps(resp_data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload_bytes)))
        self.end_headers()
        self.wfile.write(payload_bytes)

    def _handle_fs_open(self) -> None:
        """Open volume from local or remote SSH path and update active scene.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Sends JSON response with updated scene.
        """
        try:
            content_len: int = int(self.headers.get("Content-Length", 0))
            body: bytes = self.rfile.read(content_len)
            payload: dict[str, Any] = json.loads(body.decode("utf-8"))
            target_path_str: str = payload.get("path", "")
            req_host: str = (payload.get("host") or "localhost").strip()

            if req_host in ("localhost", "127.0.0.1"):
                target_path: Path = Path(target_path_str).resolve()
                if not self.is_path_permitted(target_path):
                    self.send_error(
                        403, f"Access denied: {target_path_str}"
                    )
                    return
                if not target_path.is_file():
                    self.send_error(404, f"File not found: {target_path_str}")
                    return

                scene: NiiVueSceneSpec = self._create_scene_for_path(
                    str(target_path), host="localhost"
                )
                self.server.active_scene = scene
                resp_data: dict[str, Any] = {
                    "status": "ok",
                    "host": "localhost",
                    "path": str(target_path),
                    "title": target_path.name,
                    "scene": scene.model_dump(),
                }
            else:
                explorer: LocalFileExplorer = LocalFileExplorer()
                try:
                    staged_path: Path = explorer.stage_remote_volume(
                        host=req_host, remote_path=target_path_str
                    )
                except FileNotFoundError as fnf_err:
                    self.send_error(404, str(fnf_err))
                    return

                display_name: str = (
                    os.path.basename(target_path_str.rstrip("/"))
                    or staged_path.name
                )
                scene = self._create_scene_for_path(
                    str(staged_path),
                    host=req_host,
                    display_name=display_name,
                )
                self.server.active_scene = scene
                resp_data = {
                    "status": "ok",
                    "host": req_host,
                    "path": str(staged_path),
                    "remote_path": target_path_str,
                    "title": display_name,
                    "scene": scene.model_dump(),
                }

            payload_bytes: bytes = json.dumps(resp_data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload_bytes)))
            self.end_headers()
            self.wfile.write(payload_bytes)
        except Exception as err:
            self.send_error(400, f"Failed to open file: {err}")

    def _create_scene_for_path(
        self,
        file_path_str: str,
        host: str = "localhost",
        display_name: str | None = None,
    ) -> NiiVueSceneSpec:
        """Construct NiiVueSceneSpec containing the specified volume file.

        Parameters
        ------------
        file_path_str: str
            Local filesystem path to volume file (direct or staged).
        host: str
            Source host label. Defaults to 'localhost'.
        display_name: str | None
            Optional display filename override. Defaults to None.

        Returns
        --------
            NiiVueSceneSpec: NiiVueSceneSpec instance
                Constructed declarative scene manifest.
        """
        path_obj: Path = Path(file_path_str).resolve()
        vol_name: str = display_name if display_name else path_obj.name
        title_str: str = (
            f"Neuri: {vol_name}"
            if host in ("localhost", "127.0.0.1")
            else f"Neuri [{host}]: {vol_name}"
        )
        scene_id: str = f"scene_{uuid.uuid4().hex[:8]}"
        scene: NiiVueSceneSpec = NiiVueSceneSpec(
            scene_id=scene_id,
            title=title_str,
            volumes=[
                NiiVueLayerSpec(
                    artifact_uri=str(path_obj),
                    colormap="gray",
                    opacity=1.0,
                )
            ],
            slice_type="multiplanar",
        )
        return scene

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
        """Stream local or staged neuroimaging volume bytes with Range support.

        Parameters
        ------------
        uri: str
            Raw URI or local file path string.

        Returns
        --------
            None: NoneType object
                Sends binary stream with Range support.
        """
        clean_path_str: str = uri
        if clean_path_str.startswith("file://"):
            clean_path_str = clean_path_str[7:]

        local_file: Path = Path(clean_path_str).resolve()
        if not self.is_path_permitted(local_file):
            self.send_error(403, f"Access denied: {clean_path_str}")
            return

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

        cors_origin: str = self._get_cors_origin()
        range_hdr: str | None = self.headers.get("Range")
        if range_hdr:
            match = re.match(r"^bytes=(\d*)-(\d*)$", range_hdr.strip())
            if not match:
                self.send_response(416, "Range Not Satisfiable")
                self.send_header("Access-Control-Allow-Origin", cors_origin)
                self.send_header("Content-Range", f"bytes */{total_size}")
                self.end_headers()
                return

            s_str, e_str = match.groups()
            if not s_str and not e_str:
                self.send_response(416, "Range Not Satisfiable")
                self.send_header("Access-Control-Allow-Origin", cors_origin)
                self.send_header("Content-Range", f"bytes */{total_size}")
                self.end_headers()
                return

            if not s_str:
                suffix_len: int = int(e_str)
                start: int = max(0, total_size - suffix_len)
                end: int = total_size - 1
            else:
                start = int(s_str)
                end = (
                    min(int(e_str), total_size - 1)
                    if e_str
                    else total_size - 1
                )

            if start >= total_size or start > end:
                self.send_response(416, "Range Not Satisfiable")
                self.send_header("Access-Control-Allow-Origin", cors_origin)
                self.send_header("Content-Range", f"bytes */{total_size}")
                self.end_headers()
                return

            length: int = end - start + 1

            self.send_response(206, "Partial Content")
            self.send_header("Access-Control-Allow-Origin", cors_origin)
            self.send_header(
                "Access-Control-Expose-Headers",
                "Content-Range, Content-Length, Accept-Ranges",
            )
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
            self.send_header("Access-Control-Allow-Origin", cors_origin)
            self.send_header(
                "Access-Control-Expose-Headers",
                "Content-Range, Content-Length, Accept-Ranges",
            )
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

    _instance: Any = None

    @classmethod
    def get_instance(
        cls, host: str = "127.0.0.1", port: int = 8421
    ) -> "NiiVueBridge":
        """Retrieve or create singleton NiiVueBridge instance.

        Parameters
        ------------
        host: str
            Binding host address. Defaults to '127.0.0.1'.
        port: int
            Binding port number. Defaults to 8421.

        Returns
        --------
            NiiVueBridge: NiiVueBridge instance
                Shared bridge instance.
        """
        if cls._instance is None:
            cls._instance = cls(host=host, port=port)
        inst: NiiVueBridge = cls._instance
        return inst

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
        self._server: NiiVueHTTPServer | None = None
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

        server = NiiVueHTTPServer(
            (self._host, self._port), NiiVueBridgeHandler
        )
        server.active_scene = self._active_scene
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

    @property
    def server(self) -> NiiVueHTTPServer | None:
        """Retrieve the active NiiVue HTTP server instance.

        Parameters
        ------------
        None

        Returns
        --------
            NiiVueHTTPServer | None: server instance or None
                Underlying HTTP server.
        """
        return self._server

    @property
    def latest_selection(self) -> dict[str, Any] | None:
        """Return the most recently clicked 3D voxel coordinate selection.

        Parameters
        ------------
        None

        Returns
        --------
            dict[str, Any] | None: selection dictionary or None
                Latest coordinate feedback payload.
        """
        if self._server is not None:
            return getattr(self._server, "latest_selection", None)
        return None

    @latest_selection.setter
    def latest_selection(self, val: dict[str, Any] | None) -> None:
        """Update the latest 3D voxel coordinate selection.

        Parameters
        ------------
        val: dict[str, Any] | None
            New coordinate selection payload or None to reset.

        Returns
        --------
            None: NoneType object
                Updates internal selection state.
        """
        if self._server is not None:
            self._server.latest_selection = val

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
            self._server.active_scene = scene
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
        if self._server is not None:
            srv_scene: NiiVueSceneSpec | None = getattr(
                self._server, "active_scene", None
            )
            if srv_scene is not None:
                return srv_scene
        return self._active_scene

    def create_scene_for_volume(
        self, path: Path | str
    ) -> NiiVueSceneSpec:
        """Create and push a declarative scene for a volume file.

        Parameters
        ------------
        path: Path | str
            Local volume file path.

        Returns
        --------
            NiiVueSceneSpec: NiiVueSceneSpec instance
                Created scene specification.
        """
        path_obj: Path = Path(path).resolve()
        scene_id: str = f"scene_{uuid.uuid4().hex[:8]}"
        scene: NiiVueSceneSpec = NiiVueSceneSpec(
            scene_id=scene_id,
            title=f"Neuri: {path_obj.name}",
            volumes=[
                NiiVueLayerSpec(
                    artifact_uri=str(path_obj),
                    colormap="gray",
                    opacity=1.0,
                )
            ],
            slice_type="multiplanar",
        )
        self.push_scene(scene)
        return scene


__all__: list[str] = [
    "NiiVueBridge",
    "NiiVueBridgeHandler",
    "NiiVueHTTPServer",
]
