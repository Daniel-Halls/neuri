"""Regression tests for NiiVue viewer slice modes and non-MNI volume loading.

Validates viewer HTML button-to-SLICE_TYPE mappings, fallback volume loading in
JavaScript, permission/range streaming in NiiVueBridgeHandler, and /view scene
synchronization into NeuriGUIServer.
"""

import io
import json
import subprocess
import urllib.parse
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from neuri.core.blackboard import Blackboard
from neuri.core.config import NeuriConfig
from neuri.core.session import NeuriSessionEngine
from neuri.gui.server import NeuriGUIHandler, NeuriGUIServer, resolve_gui_static_dir
from neuri.ui.history import PromptHistoryManager
from neuri.ui.theme import NeuriThemeManager
from neuri.viewer.local_explorer import LocalFileExplorer
from neuri.viewer.niivue_bridge import NiiVueBridgeHandler, NiiVueHTTPServer


class MemorySocket:
    """In-memory bidirectional socket stub for BaseHTTPRequestHandler tests.

    Parameters
    ------------
    data: bytes
        Raw HTTP request bytes buffered for reading.

    Returns
    --------
        MemorySocket: MemorySocket instance
            Constructed in-memory socket double.
    """

    def __init__(self, data: bytes) -> None:
        """Initialize read/write byte buffers.

        Parameters
        ------------
        data: bytes
            Raw HTTP request wire bytes.

        Returns
        --------
            None: NoneType object
                Initializes internal BytesIO streams.
        """
        self._r: io.BytesIO = io.BytesIO(data)
        self._w: io.BytesIO = io.BytesIO()

    def makefile(self, mode: str, *args: Any, **kwargs: Any) -> Any:
        """Return underlying byte stream corresponding to file mode.

        Parameters
        ------------
        mode: str
            Stream mode string containing 'r' or 'w'.
        *args: Any
            Unused positional buffering arguments.
        **kwargs: Any
            Unused keyword buffering arguments.

        Returns
        --------
            io.BytesIO: BytesIO object
                Input or output memory buffer.
        """
        return self._r if "r" in mode else self._w

    def sendall(self, data: bytes) -> None:
        """Write response bytes into output buffer.

        Parameters
        ------------
        data: bytes
            Raw bytes emitted by HTTP handler.

        Returns
        --------
            None: NoneType object
                Appends response payload bytes.
        """
        self._w.write(data)


def _dispatch_handler_request(
    handler_cls: type[Any],
    server: Any,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    extra_headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    """Dispatch an in-memory HTTP request directly to an HTTP handler class.

    Parameters
    ------------
    handler_cls: type[Any]
        Handler class such as NiiVueBridgeHandler or NeuriGUIHandler.
    server: Any
        Server instance attached to handler_cls.
    method: str
        HTTP verb ('GET', 'POST', 'HEAD').
    path: str
        Request URI path with optional query string.
    body: dict[str, Any] | None
        Optional JSON payload for POST requests. Defaults to None.
    extra_headers: dict[str, str] | None
        Optional extra HTTP headers. Defaults to None.

    Returns
    --------
        tuple[int, dict[str, str], bytes]: tuple object
            Tuple of (status_code, headers_lower_dict, body_bytes).
    """
    payload_bytes: bytes = (
        json.dumps(body).encode("utf-8") if body is not None else b""
    )
    req_lines: list[str] = [
        f"{method} {path} HTTP/1.1",
        "Host: 127.0.0.1",
        "Content-Type: application/json",
        f"Content-Length: {len(payload_bytes)}",
    ]
    if extra_headers:
        for hdr_key, hdr_val in extra_headers.items():
            req_lines.append(f"{hdr_key}: {hdr_val}")
    req_lines.extend(["", ""])
    raw_req: bytes = "\r\n".join(req_lines).encode("utf-8") + payload_bytes

    sock: MemorySocket = MemorySocket(raw_req)
    handler_cls(sock, ("127.0.0.1", 12345), server)
    raw_resp: bytes = sock._w.getvalue()

    parts: list[bytes] = raw_resp.split(b"\r\n\r\n", 1)
    headers_text: str = parts[0].decode("utf-8", errors="replace")
    resp_body: bytes = parts[1] if len(parts) > 1 else b""

    status_code: int = int(headers_text.splitlines()[0].split()[1])
    headers: dict[str, str] = {}
    for line in headers_text.splitlines()[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    return (status_code, headers, resp_body)


def test_viewer_slice_buttons_and_loader_in_node() -> None:
    """Verify slice buttons map to exact NiiVue SLICE_TYPE values and fallback loads.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Runs viewer script via Node vm and asserts behavior.
    """
    viewer_html: Path = (
        Path(__file__).resolve().parent.parent.parent
        / "src"
        / "neuri"
        / "viewer"
        / "static"
        / "index.html"
    )
    node_script: str = """
const fs = require("fs");
const vm = require("vm");
const assert = require("assert");

const html = fs.readFileSync(process.argv[1], "utf8");
const scriptRe = /<script(?:\\s+[^>]*)?>([\\s\\S]*?)<\\/script>/g;
const scripts = [...html.matchAll(scriptRe)]
  .map((m) => m[1])
  .filter((s) => s.trim().length > 0)
  .join("\\n");

const btnMap = {};
const btnRe = new RegExp(
  '<button id="(btn-(?:multi|axial|coronal|sagittal|3d))"[^>]*onclick="([^"]+)"',
  "g"
);
for (const m of html.matchAll(btnRe)) {
  btnMap[m[1]] = m[2];
}
assert.strictEqual(Object.keys(btnMap).length, 5, "Expected 5 view buttons");

function makeElement(id) {
  const classes = new Set();
  return {
    id,
    innerText: "",
    textContent: "",
    innerHTML: "",
    value: "",
    disabled: false,
    style: {},
    children: [],
    appendChild(c) { this.children.push(c); },
    addEventListener() {},
    classList: {
      add(c) { classes.add(c); },
      remove(c) { classes.delete(c); },
      toggle(c, force) {
        if (force === undefined) {
          if (classes.has(c)) classes.delete(c); else classes.add(c);
        } else if (force) {
          classes.add(c);
        } else {
          classes.delete(c);
        }
      },
      contains(c) { return classes.has(c); },
    },
  };
}

const elements = {};
for (const m of html.matchAll(/id=["']([^"']+)["']/g)) {
  elements[m[1]] = makeElement(m[1]);
}

const sliceCalls = [];
const loadedCalls = [];
let mockLoadVolumesShouldFail = false;

const mockNvInstance = {
  sliceTypeAxial: 0,
  sliceTypeCoronal: 1,
  sliceTypeSagittal: 2,
  sliceTypeMultiplanar: 3,
  sliceTypeRender: 4,
  volumes: [],
  meshes: [],
  opts: {},
  async attachTo() {},
  setSliceType(val) { sliceCalls.push(val); },
  async loadVolumes(vols) {
    if (mockLoadVolumesShouldFail) throw new Error("url load rejected");
    loadedCalls.push({ method: "loadVolumes", vols });
    this.volumes = vols;
  },
  async loadImages(imgs) {
    loadedCalls.push({ method: "loadImages", imgs });
    this.meshes = imgs;
  },
  async loadFromFile(file) {
    loadedCalls.push({
      method: "loadFromFile",
      name: file.name,
      size: file.size,
    });
    this.volumes = [{ name: file.name }];
  },
};

const listeners = {};
let activeScenePayload = {};
const blobUrls = new Map();
let blobCounter = 0;

class FakeFile {
  constructor(parts, name) {
    this.parts = parts;
    this.name = name;
    this.size = parts.reduce(
      (acc, p) => acc + (p.byteLength || p.length || 0), 0
    );
  }
  async arrayBuffer() {
    return new Uint8Array([1, 2, 3, 4]).buffer;
  }
}

class FakeBlob {
  constructor(parts) {
    this.parts = parts;
  }
}

const context = {
  console,
  URL: class FakeURL {
    constructor(input, base) {
      if (!base && !/^https?:/.test(input)) throw new Error("base required");
      this.href = /^https?:|^blob:/.test(input)
        ? input
        : base.replace(/\\/$/, "") + input;
    }
    static createObjectURL(obj) {
      blobCounter += 1;
      const u = "blob:http://127.0.0.1:8420/obj-" + blobCounter;
      blobUrls.set(u, obj);
      return u;
    }
    static revokeObjectURL(u) {
      blobUrls.delete(u);
    }
  },
  File: FakeFile,
  Blob: FakeBlob,
  window: {
    location: { origin: "http://127.0.0.1:8420" },
    addEventListener(name, fn) { listeners[name] = fn; },
    parent: null,
  },
  document: {
    body: makeElement("body"),
    getElementById(id) {
      return elements[id] || null;
    },
    createElement(tag) { return makeElement(tag); },
    querySelectorAll() { return []; },
  },
  niivue: {
    SLICE_TYPE: {
      AXIAL: 0, CORONAL: 1, SAGITTAL: 2, MULTIPLANAR: 3, RENDER: 4
    },
    Niivue: function() { return mockNvInstance; },
  },
  fetch: async (url) => {
    if (String(url).endsWith("/api/scene")) {
      return { ok: true, status: 200, json: async () => activeScenePayload };
    }
    if (String(url).endsWith("/api/hosts")) {
      return {
        ok: true,
        status: 200,
        json: async () => ({
          hosts: ["localhost"], default_host: "localhost"
        }),
      };
    }
    return {
      ok: true,
      status: 200,
      arrayBuffer: async () => new Uint8Array([9, 8, 7, 6]).buffer,
    };
  },
  setInterval() { return 1; },
  setTimeout,
  clearTimeout,
};
context.window.window = context.window;

async function main() {
  vm.runInNewContext(scripts, context);
  await context.initNiiVue();

  // Clicking every button triggers exact NiiVue SLICE_TYPE value
  sliceCalls.length = 0;
  vm.runInNewContext(btnMap["btn-axial"], context);
  assert.strictEqual(sliceCalls.pop(), 0, "Axial must map to 0");
  assert(elements["btn-axial"].classList.contains("active"));
  assert(!elements["btn-multi"].classList.contains("active"));

  vm.runInNewContext(btnMap["btn-coronal"], context);
  assert.strictEqual(sliceCalls.pop(), 1, "Coronal must map to 1");
  assert(elements["btn-coronal"].classList.contains("active"));

  vm.runInNewContext(btnMap["btn-sagittal"], context);
  assert.strictEqual(sliceCalls.pop(), 2, "Sagittal must map to 2");
  assert(elements["btn-sagittal"].classList.contains("active"));
  assert(!elements["btn-3d"].classList.contains("active"));

  vm.runInNewContext(btnMap["btn-3d"], context);
  assert.strictEqual(sliceCalls.pop(), 4, "3D must map to 4");
  assert(elements["btn-3d"].classList.contains("active"));
  assert(!elements["btn-sagittal"].classList.contains("active"));

  vm.runInNewContext(btnMap["btn-multi"], context);
  assert.strictEqual(sliceCalls.pop(), 3, "Multi must map to 3");
  assert(elements["btn-multi"].classList.contains("active"));

  // applyLoadedVolume resolves relative URLs & supports loadFromFile fallback
  loadedCalls.length = 0;
  mockLoadVolumesShouldFail = false;
  await context.applyLoadedVolume({
    status: "ok",
    host: "localhost",
    path: "/Volumes/MRI/sub 01_T1w.nii.gz",
    title: "sub 01_T1w.nii.gz",
    scene: {
      scene_id: "scene_vol1", title: "Neuri: sub 01_T1w.nii.gz", volumes: []
    },
  });
  assert.strictEqual(loadedCalls[0].method, "loadVolumes");
  assert(
    loadedCalls[0].vols[0].url.startsWith("http://127.0.0.1:8420/api/file/"),
    "Must resolve relative /api/file URL to full origin URL"
  );

  // When loadVolumes rejects and loadFromArrayBuffer is absent, use loadFromFile
  loadedCalls.length = 0;
  mockLoadVolumesShouldFail = true;
  await context.applyLoadedVolume({
    status: "ok",
    host: "localhost",
    path: "/data/fallback_brain.nii.gz",
    title: "fallback_brain.nii.gz",
    scene: { scene_id: "scene_vol2", title: "Fallback", volumes: [] },
  });
  assert.strictEqual(loadedCalls[0].method, "loadFromFile");
  assert.strictEqual(loadedCalls[0].name, "fallback_brain.nii.gz");

  // Mesh files (.gii) route to loadImages
  loadedCalls.length = 0;
  mockLoadVolumesShouldFail = false;
  await context.applyLoadedVolume({
    status: "ok",
    host: "localhost",
    path: "/data/cortex.surf.gii",
    title: "cortex.surf.gii",
    scene: { scene_id: "scene_mesh", title: "Mesh", volumes: [] },
  });
  assert.strictEqual(loadedCalls[0].method, "loadImages");

  // Local upload is not overwritten when pollScene returns older backend scene
  activeScenePayload = {
    scene_id: "scene_mesh",
    title: "Old Scene",
    volumes: [{ artifact_uri: "/data/cortex.surf.gii", opacity: 1.0 }],
  };
  await context.pollScene();
  const fakeLocal = new FakeFile([new Uint8Array([1, 2, 3])], "up_T1w.nii.gz");
  await context.handleLocalFileObject(fakeLocal);
  loadedCalls.length = 0;
  await context.pollScene();
  assert.strictEqual(loadedCalls.length, 0, "Stale poll overwrote upload");

  // Brand-new backend scene_id (e.g. from /view) does update the viewer
  activeScenePayload = {
    scene_id: "scene_new_view",
    title: "Neuri: new_scan.nii.gz",
    slice_type: "sagittal",
    volumes: [{ artifact_uri: "/Volumes/Data/new_scan.nii.gz", opacity: 1.0 }],
  };
  await context.pollScene();
  assert.strictEqual(loadedCalls[0].method, "loadVolumes");
  assert.strictEqual(sliceCalls.pop(), 2, "Sagittal scene must map to 2");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
"""
    proc: subprocess.CompletedProcess[str] = subprocess.run(
        ["node", "-e", node_script, str(viewer_html)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, (
        f"Node viewer check failed:\n{proc.stderr}\n{proc.stdout}"
    )


def test_niivue_bridge_allows_any_non_sensitive_volume_and_head(
    tmp_path: Path,
) -> None:
    """Verify NiiVueBridgeHandler opens volumes outside cwd while blocking .ssh.

    Parameters
    ------------
    tmp_path: Path
        Temporary directory outside workspace cwd.

    Returns
    --------
        None: NoneType object
            Asserts GET/POST/HEAD behavior and 403 guard on ~/.ssh.
    """
    vol_dir: Path = tmp_path / "external_mri"
    vol_dir.mkdir()
    spaced_vol: Path = vol_dir / "my brain scan.nii.gz"
    spaced_vol.write_bytes(b"NII_GZ_TEST_BYTES_12345")

    server: NiiVueHTTPServer = NiiVueHTTPServer(
        ("127.0.0.1", 0), NiiVueBridgeHandler
    )
    server.server_close()

    # 1. Directory listing outside cwd succeeds
    list_path: str = (
        f"/api/fs/list?host=localhost&path={urllib.parse.quote(str(vol_dir))}"
    )
    status, _hdrs, body = _dispatch_handler_request(
        NiiVueBridgeHandler, server, "GET", list_path
    )
    assert status == 200
    listing: dict[str, Any] = json.loads(body.decode("utf-8"))
    assert listing["current_path"] == str(vol_dir.resolve())
    assert any(e["name"] == "my brain scan.nii.gz" for e in listing["entries"])

    # 2. Opening non-cwd volume succeeds
    status_open, _hdrs_open, body_open = _dispatch_handler_request(
        NiiVueBridgeHandler,
        server,
        "POST",
        "/api/fs/open",
        body={"path": str(spaced_vol), "host": "localhost"},
    )
    assert status_open == 200
    open_json: dict[str, Any] = json.loads(body_open.decode("utf-8"))
    assert open_json["status"] == "ok"

    # 3. Streaming with file:// URL-encoded URI + Range + HEAD succeeds
    file_uri_encoded: str = urllib.parse.quote(spaced_vol.resolve().as_uri())
    stream_url: str = (
        f"/api/file/{urllib.parse.quote(spaced_vol.name)}?uri={file_uri_encoded}"
    )
    st_head, hdr_head, body_head = _dispatch_handler_request(
        NiiVueBridgeHandler, server, "HEAD", stream_url
    )
    assert st_head == 200
    assert hdr_head.get("content-length") == str(len(b"NII_GZ_TEST_BYTES_12345"))
    assert body_head == b""

    st_get, hdr_get, body_get = _dispatch_handler_request(
        NiiVueBridgeHandler, server, "GET", stream_url
    )
    assert st_get == 200
    assert hdr_get.get("content-type") == "application/octet-stream"
    assert body_get == b"NII_GZ_TEST_BYTES_12345"

    st_rng, hdr_rng, body_rng = _dispatch_handler_request(
        NiiVueBridgeHandler,
        server,
        "GET",
        stream_url,
        extra_headers={"Range": "bytes=0-6"},
    )
    assert st_rng == 206
    assert hdr_rng.get("content-range") == "bytes 0-6/23"
    assert body_rng == b"NII_GZ_"

    # 4. Sensitive credential directories remain forbidden
    ssh_secret: Path = Path.home() / ".ssh" / "id_rsa"
    st_ssh, _hdr_ssh, _body_ssh = _dispatch_handler_request(
        NiiVueBridgeHandler,
        server,
        "GET",
        f"/api/file/id_rsa?uri={urllib.parse.quote(str(ssh_secret))}",
    )
    assert st_ssh == 403


def test_gui_server_syncs_view_slash_command_to_active_scene(
    tmp_path: Path,
) -> None:
    """Verify /view <path> in Studio GUI updates NeuriGUIServer /api/scene.

    Parameters
    ------------
    tmp_path: Path
        Temporary directory fixture containing synthetic workspace and volume.

    Returns
    --------
        None: NoneType object
            Asserts POST /api/v1/input triggers GET /api/scene update.
    """
    ws_dir: Path = tmp_path / "workspace"
    ws_dir.mkdir()
    vol_file: Path = ws_dir / "sub-02_FLAIR.nii.gz"
    vol_file.write_bytes(b"FLAIR_DATA")

    bb: Blackboard = Blackboard(ws_dir / ".neuri" / "state.db")
    cfg: NeuriConfig = NeuriConfig()
    engine: NeuriSessionEngine = NeuriSessionEngine(
        workspace_dir=ws_dir, config=cfg, blackboard=bb
    )
    theme_mgr: NeuriThemeManager = NeuriThemeManager(workspace_dir=ws_dir)
    hist_mgr: PromptHistoryManager = PromptHistoryManager(
        history_file=ws_dir / ".neuri" / "history"
    )
    server: NeuriGUIServer = NeuriGUIServer(
        ("127.0.0.1", 0),
        session_engine=engine,
        theme_manager=theme_mgr,
        history_manager=hist_mgr,
        static_dir=resolve_gui_static_dir(),
    )
    server.server_close()

    st_in, _hdr_in, _body_in = _dispatch_handler_request(
        NeuriGUIHandler,
        server,
        "POST",
        "/api/v1/input",
        body={"text": f"/view {vol_file} --no-open"},
    )
    assert st_in == 200

    st_sc, _hdr_sc, body_sc = _dispatch_handler_request(
        NeuriGUIHandler, server, "GET", "/api/scene"
    )
    assert st_sc == 200
    scene: dict[str, Any] = json.loads(body_sc.decode("utf-8"))
    assert scene["title"] == "Neuri: sub-02_FLAIR.nii.gz"
    assert scene["volumes"][0]["artifact_uri"] == str(vol_file)


def test_local_explorer_extended_formats_and_macos_error_reporting() -> None:
    """Verify extended volume/mesh extensions and macOS dialog error reporting.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Confirms new formats match and AppleScript errors surface clearly.
    """
    explorer: LocalFileExplorer = LocalFileExplorer()
    for fname in (
        "dwi.nrrd",
        "dwi.nhdr",
        "cortex.gii",
        "surface.mz3",
        "tract.vtk",
        "bold.nii.zst",
        "slice.ima",
    ):
        assert explorer.is_volume_file(fname) is True

    fake_err = MagicMock(returncode=1, stdout="", stderr="Not authorized (-1743)")
    with (
        patch(
            "neuri.viewer.local_explorer.shutil.which",
            return_value="/usr/bin/osascript",
        ),
        patch(
            "neuri.viewer.local_explorer.subprocess.run",
            return_value=fake_err,
        ),
        patch.object(
            explorer,
            "_pick_file_tkinter",
            return_value={"status": "unsupported", "message": "No display"},
        ),
    ):
        outcome: dict[str, Any] = explorer._pick_file_macos()
        assert outcome["status"] == "unsupported"
        assert "-1743" in outcome["message"]
