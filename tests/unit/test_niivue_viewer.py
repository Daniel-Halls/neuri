"""Unit tests for NiiVue WebGL2 visualization bridge and headless QA generator.

Tests byte-range partial content streaming (206), directory whitelist security,
pure-Python PNG snapshot generation (<200 KB), and NiiVueBridge scene updates.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from neuri.core.schemas import NiiVueLayerSpec, NiiVueSceneSpec
from neuri.viewer.local_explorer import LocalFileExplorer
from neuri.viewer.niivue_bridge import NiiVueBridge
from neuri_worker.headless_qa import HeadlessQAGenerator
from neuri_worker.range_server import ByteRangeHTTPServer
from tests.unit.test_sanitizer import create_synthetic_nifti_bytes


def test_byte_range_http_server_partial_content(tmp_path: Path) -> None:
    """Test ByteRangeHTTPServer serves 206 Partial Content for byte-range requests.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts 206 status, byte slicing, and Content-Range header.
    """
    test_file: Path = tmp_path / "stream_target.dat"
    payload: bytes = b"0123456789" * 100  # 1000 bytes
    test_file.write_bytes(payload)

    server: ByteRangeHTTPServer = ByteRangeHTTPServer(
        host="127.0.0.1",
        port=0,
        allowed_roots=[tmp_path],
    )
    server.start()
    port: int = server.get_server_port()

    try:
        url: str = f"http://127.0.0.1:{port}{test_file.resolve()}"
        req = urllib.request.Request(url, headers={"Range": "bytes=10-29"})
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 206
            assert resp.headers.get("Content-Range") == "bytes 10-29/1000"
            chunk = resp.read()
            assert chunk == payload[10:30]
    finally:
        server.stop()


def test_byte_range_server_forbids_unwhitelisted_paths(tmp_path: Path) -> None:
    """Test ByteRangeHTTPServer returns 403 Forbidden for disallowed paths.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory.

    Returns
    --------
        None: NoneType object
            Asserts HTTP 403 rejection.
    """
    allowed_dir: Path = tmp_path / "allowed"
    allowed_dir.mkdir()
    forbidden_dir: Path = tmp_path / "forbidden"
    forbidden_dir.mkdir()

    secret_file: Path = forbidden_dir / "secret.dat"
    secret_file.write_text("classified data")

    server: ByteRangeHTTPServer = ByteRangeHTTPServer(
        host="127.0.0.1",
        port=0,
        allowed_roots=[allowed_dir],
    )
    server.start()
    port: int = server.get_server_port()

    try:
        url: str = f"http://127.0.0.1:{port}{secret_file.resolve()}"
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(url)
        assert exc_info.value.code == 403
    finally:
        server.stop()


def test_headless_qa_orthographic_snapshot(tmp_path: Path) -> None:
    """Test HeadlessQAGenerator creates valid PNG snapshot under 200 KB.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory.

    Returns
    --------
        None: NoneType object
            Asserts PNG signature, file size bound, and dimensions.
    """
    nii_data: bytes = create_synthetic_nifti_bytes(dim_x=20, dim_y=20, dim_z=20)
    vol_path: Path = tmp_path / "sub-01_T1w.nii"
    vol_path.write_bytes(nii_data)

    qa_dir: Path = tmp_path / "qa_out"
    generator: HeadlessQAGenerator = HeadlessQAGenerator(output_dir=qa_dir)
    report = generator.generate_orthographic_snapshot(vol_path)

    snapshot_path: Path = Path(report["snapshot_path"])
    assert snapshot_path.is_file()
    assert report["quality_status"] == "OK"
    assert report["file_size_bytes"] < 200000

    # Validate standard 8-byte PNG header signature
    content: bytes = snapshot_path.read_bytes()
    assert content.startswith(b"\x89PNG\r\n\x1a\n")


def test_headless_qa_registration_overlay(tmp_path: Path) -> None:
    """Test HeadlessQAGenerator creates RGB contour registration overlay.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory.

    Returns
    --------
        None: NoneType object
            Asserts overlay PNG generated.
    """
    fixed_data: bytes = create_synthetic_nifti_bytes(dim_x=16, dim_y=16, dim_z=16)
    moving_data: bytes = create_synthetic_nifti_bytes(dim_x=16, dim_y=16, dim_z=16)

    fixed_file: Path = tmp_path / "fixed_T1w.nii"
    moving_file: Path = tmp_path / "moving_T1w.nii"
    fixed_file.write_bytes(fixed_data)
    moving_file.write_bytes(moving_data)

    qa_dir: Path = tmp_path / "qa_reg"
    generator: HeadlessQAGenerator = HeadlessQAGenerator(output_dir=qa_dir)
    report = generator.generate_registration_overlay(fixed_file, moving_file)

    overlay_file: Path = Path(report["snapshot_path"])
    assert overlay_file.is_file()
    assert report["quality_status"] == "OK"
    assert report["file_size_bytes"] < 200000


def test_niivue_bridge_scene_dispatch() -> None:
    """Test NiiVueBridge push_scene and REST endpoint synchronization.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts scene state push and query.
    """
    bridge: NiiVueBridge = NiiVueBridge(host="127.0.0.1", port=0)
    bridge.start()

    try:
        scene = NiiVueSceneSpec(
            scene_id="scene_001",
            title="T1w Structural View",
            volumes=[
                NiiVueLayerSpec(
                    artifact_uri="/data/sub-01/T1w.nii.gz",
                    colormap="gray",
                    opacity=1.0,
                )
            ],
            slice_type="multiplanar",
        )
        ok: bool = bridge.push_scene(scene)
        assert ok is True

        retrieved: NiiVueSceneSpec | None = bridge.get_scene()
        assert retrieved is not None
        assert retrieved.scene_id == "scene_001"
        assert retrieved.title == "T1w Structural View"
    finally:
        bridge.stop()


def test_local_file_explorer_volume_detection() -> None:
    """Verify LocalFileExplorer correctly classifies neuroimaging volume extensions.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts extension matching behavior.
    """
    explorer: LocalFileExplorer = LocalFileExplorer()
    assert explorer.is_volume_file("sub-01_T1w.nii") is True
    assert explorer.is_volume_file("sub-01_T1w.nii.gz") is True
    assert explorer.is_volume_file("brain.mgz") is True
    assert explorer.is_volume_file("brain.mgh") is True
    assert explorer.is_volume_file("slice.dcm") is True
    assert explorer.is_volume_file("notes.txt") is False
    assert explorer.is_volume_file("pipeline.py") is False
    assert explorer.is_volume_file("preview.png") is False


def test_local_file_explorer_size_formatting() -> None:
    """Verify LocalFileExplorer format_file_size returns human-readable units.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts byte, KB, MB, and GB formatting strings.
    """
    explorer: LocalFileExplorer = LocalFileExplorer()
    assert explorer.format_file_size(500) == "500 B"
    assert explorer.format_file_size(2048) == "2.0 KB"
    assert explorer.format_file_size(15 * 1024 * 1024) == "15.0 MB"
    assert explorer.format_file_size(2 * 1024 * 1024 * 1024) == "2.00 GB"


def test_local_file_explorer_list_directory(tmp_path: Path) -> None:
    """Verify LocalFileExplorer lists entries, tags volumes, and navigates.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts directory entry classification and path metadata.
    """
    sub_dir: Path = tmp_path / "anat"
    sub_dir.mkdir()
    vol_file: Path = sub_dir / "sub-01_T1w.nii.gz"
    vol_file.write_bytes(b"dummy volume data")
    txt_file: Path = sub_dir / "readme.txt"
    txt_file.write_text("dataset documentation")

    explorer: LocalFileExplorer = LocalFileExplorer(default_dir=tmp_path)

    # Test listing parent directory
    top_listing: dict[str, Any] = explorer.list_directory(str(tmp_path))
    assert top_listing["current_path"] == str(tmp_path.resolve())
    assert top_listing["workspace_path"] == str(tmp_path.resolve())
    assert any(
        e["name"] == "anat" and e["is_dir"] is True
        for e in top_listing["entries"]
    )

    # Test listing anat directory
    anat_listing: dict[str, Any] = explorer.list_directory(str(sub_dir))
    assert anat_listing["current_path"] == str(sub_dir.resolve())
    assert anat_listing["parent_path"] == str(tmp_path.resolve())

    vol_entry = next(
        e for e in anat_listing["entries"] if e["name"] == "sub-01_T1w.nii.gz"
    )
    assert vol_entry["is_volume"] is True
    assert vol_entry["is_dir"] is False
    assert vol_entry["size_bytes"] > 0

    txt_entry = next(
        e for e in anat_listing["entries"] if e["name"] == "readme.txt"
    )
    assert txt_entry["is_volume"] is False
    assert txt_entry["is_dir"] is False


def test_niivue_bridge_fs_endpoints(tmp_path: Path) -> None:
    """Test NiiVueBridge /api/fs/list and /api/fs/open REST endpoints.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts JSON responses, scene creation, and 404 for invalid files.
    """
    test_vol: Path = tmp_path / "sample_brain.nii.gz"
    test_vol.write_bytes(b"synthetic nifti payload")

    bridge: NiiVueBridge = NiiVueBridge(host="127.0.0.1", port=0)
    bridge.start()

    try:
        base_url: str = bridge.get_url()

        # 1. Test GET /api/fs/list
        list_url: str = (
            f"{base_url}/api/fs/list?path={urllib.parse.quote(str(tmp_path))}"
        )
        with urllib.request.urlopen(list_url) as resp:
            assert resp.status == 200
            data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
            assert data["current_path"] == str(tmp_path.resolve())
            assert any(
                e["name"] == "sample_brain.nii.gz" and e["is_volume"] is True
                for e in data["entries"]
            )

        # 2. Test POST /api/fs/open with valid volume path
        open_url: str = f"{base_url}/api/fs/open"
        post_data: bytes = json.dumps({"path": str(test_vol)}).encode("utf-8")
        req = urllib.request.Request(
            open_url, data=post_data, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            open_res: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
            assert open_res["status"] == "ok"
            assert open_res["path"] == str(test_vol.resolve())
            assert open_res["title"] == "sample_brain.nii.gz"

        active_scene: NiiVueSceneSpec | None = bridge.get_scene()
        assert active_scene is not None
        assert len(active_scene.volumes) == 1
        assert active_scene.volumes[0].artifact_uri == str(test_vol.resolve())

        # 3. Test POST /api/fs/open with non-existent file path returns 404
        non_existent_data: bytes = json.dumps(
            {"path": str(tmp_path / "does_not_exist.nii")}
        ).encode("utf-8")
        req_bad = urllib.request.Request(
            open_url,
            data=non_existent_data,
            headers={"Content-Type": "application/json"},
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req_bad)
        assert exc_info.value.code == 404

        # 4. Test GET /api/file/<filename>?uri=...
        file_stream_url: str = (
            f"{base_url}/api/file/sample_brain.nii.gz?uri="
            f"{urllib.parse.quote(str(test_vol))}"
        )
        with urllib.request.urlopen(file_stream_url) as resp:
            assert resp.status == 200
            assert resp.read() == b"synthetic nifti payload"
            assert resp.headers.get("Access-Control-Allow-Origin") == "*"

    finally:
        bridge.stop()


def test_niivue_bridge_open_dialog_endpoint(tmp_path: Path) -> None:
    """Test NiiVueBridge /api/open-dialog endpoint with mocked native picker.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts native file selection triggers scene update.
    """
    selected_vol: Path = tmp_path / "picked_volume.nii.gz"
    selected_vol.write_bytes(b"picked volume bytes")

    bridge: NiiVueBridge = NiiVueBridge(host="127.0.0.1", port=0)
    bridge.start()

    try:
        base_url: str = bridge.get_url()
        dialog_url: str = f"{base_url}/api/open-dialog"

        # Mock LocalFileExplorer.pick_file_dialog to simulate user picking file
        with patch.object(
            LocalFileExplorer,
            "pick_file_dialog",
            return_value={"status": "ok", "path": str(selected_vol)},
        ):
            req = urllib.request.Request(
                dialog_url, data=b"", headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req) as resp:
                assert resp.status == 200
                res_data: dict[str, Any] = json.loads(
                    resp.read().decode("utf-8")
                )
                assert res_data["status"] == "ok"
                assert res_data["path"] == str(selected_vol)
                assert res_data["title"] == "picked_volume.nii.gz"

        active_scene = bridge.get_scene()
        assert active_scene is not None
        assert active_scene.volumes[0].artifact_uri == str(selected_vol)

        # Test user cancellation
        with patch.object(
            LocalFileExplorer,
            "pick_file_dialog",
            return_value={"status": "canceled"},
        ):
            req_cancel = urllib.request.Request(
                dialog_url, data=b"", headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req_cancel) as resp:
                assert resp.status == 200
                cancel_data = json.loads(resp.read().decode("utf-8"))
                assert cancel_data["status"] == "canceled"

    finally:
        bridge.stop()


def test_local_file_explorer_remote_ssh_and_staging(tmp_path: Path) -> None:
    """Test LocalFileExplorer remote SSH directory listing and volume staging.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts remote listing parsing and local staging cache behavior.
    """
    cache_dir: Path = tmp_path / "viewer_cache"
    explorer: LocalFileExplorer = LocalFileExplorer(
        default_dir=tmp_path, cache_root=cache_dir
    )

    hosts_info: dict[str, Any] = explorer.get_available_hosts()
    assert "localhost" in hosts_info["hosts"]
    assert isinstance(hosts_info["default_host"], str)

    remote_payload: dict[str, Any] = {
        "current_path": "/remote/bids/sub-01/anat",
        "parent_path": "/remote/bids/sub-01",
        "home_path": "/home/researcher",
        "workspace_path": "/remote/bids",
        "entries": [
            {
                "name": "sub-01_T1w.nii.gz",
                "path": "/remote/bids/sub-01/anat/sub-01_T1w.nii.gz",
                "is_dir": False,
                "is_volume": True,
                "size_bytes": 1048576,
                "size_formatted": "1.0 MB",
                "modified": "2026-10-28 12:00",
            }
        ],
    }

    class DummyCompletedProcess:
        """Mock subprocess.CompletedProcess for SSH calls.

        Parameters
        ------------
        returncode: int
            Process exit code.
        stdout: str
            Captured standard output string.
        stderr: str
            Captured standard error string.

        Returns
        --------
            DummyCompletedProcess: DummyCompletedProcess instance
                Mock completed process object.
        """

        def __init__(
            self, returncode: int, stdout: str = "", stderr: str = ""
        ) -> None:
            """Initialize mock completed process.

            Parameters
            ------------
            returncode: int
                Process exit code.
            stdout: str
                Standard output string. Defaults to ''.
            stderr: str
                Standard error string. Defaults to ''.

            Returns
            --------
                None: NoneType object
                    Initializes attributes.
            """
            self.returncode: int = returncode
            self.stdout: str = stdout
            self.stderr: str = stderr

    with patch(
        "neuri.viewer.local_explorer.subprocess.run",
        return_value=DummyCompletedProcess(
            returncode=0, stdout=json.dumps(remote_payload)
        ),
    ):
        listing: dict[str, Any] = explorer.list_directory(
            dir_path="/remote/bids/sub-01/anat", host="gpu-node"
        )
        assert listing["host"] == "gpu-node"
        assert listing["current_path"] == "/remote/bids/sub-01/anat"
        assert len(listing["entries"]) == 1
        assert listing["entries"][0]["name"] == "sub-01_T1w.nii.gz"

    def fake_ssh_cat(cmd: list[str], **kwargs: Any) -> Any:
        """Simulate SSH cat writing volume bytes to stdout file handle.

        Parameters
        ------------
        cmd: list[str]
            Command argument list.
        **kwargs: Any
            Subprocess keyword arguments including stdout file handle.

        Returns
        --------
            DummyCompletedProcess: DummyCompletedProcess instance
                Simulated successful SSH execution.
        """
        out_f = kwargs.get("stdout")
        if out_f is not None:
            out_f.write(b"remote nifti bytes payload")
        proc_res: DummyCompletedProcess = DummyCompletedProcess(returncode=0)
        return proc_res

    with patch(
        "neuri.viewer.local_explorer.subprocess.run", side_effect=fake_ssh_cat
    ):
        staged: Path = explorer.stage_remote_volume(
            host="gpu-node",
            remote_path="/remote/bids/sub-01/anat/sub-01_T1w.nii.gz",
        )
        assert staged.is_file()
        assert staged.read_bytes() == b"remote nifti bytes payload"
        assert staged.name.endswith("_sub-01_T1w.nii.gz")


def test_niivue_bridge_remote_host_endpoints(tmp_path: Path) -> None:
    """Test NiiVueBridge /api/hosts and remote /api/fs/open endpoints.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts host discovery and remote volume staging via HTTP bridge.
    """
    staged_vol: Path = tmp_path / "staged_sub-01_T1w.nii.gz"
    staged_vol.write_bytes(b"staged remote volume data")

    bridge: NiiVueBridge = NiiVueBridge(host="127.0.0.1", port=0)
    bridge.start()

    try:
        base_url: str = bridge.get_url()

        # 1. Test GET /api/hosts
        hosts_url: str = f"{base_url}/api/hosts"
        with urllib.request.urlopen(hosts_url) as resp:
            assert resp.status == 200
            hosts_data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
            assert "localhost" in hosts_data["hosts"]

        # 2. Test POST /api/fs/open with remote host
        open_url: str = f"{base_url}/api/fs/open"
        with patch.object(
            LocalFileExplorer,
            "stage_remote_volume",
            return_value=staged_vol,
        ):
            post_body: bytes = json.dumps(
                {
                    "host": "hpc-cluster",
                    "path": "/scratch/bids/sub-01_T1w.nii.gz",
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                open_url,
                data=post_body,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req) as resp:
                assert resp.status == 200
                open_res: dict[str, Any] = json.loads(
                    resp.read().decode("utf-8")
                )
                assert open_res["status"] == "ok"
                assert open_res["host"] == "hpc-cluster"
                assert open_res["path"] == str(staged_vol)
                assert (
                    open_res["remote_path"]
                    == "/scratch/bids/sub-01_T1w.nii.gz"
                )
                assert open_res["title"] == "sub-01_T1w.nii.gz"

        scene: NiiVueSceneSpec | None = bridge.get_scene()
        assert scene is not None
        assert scene.title == "Neuri [hpc-cluster]: sub-01_T1w.nii.gz"
        assert scene.volumes[0].artifact_uri == str(staged_vol.resolve())
    finally:
        bridge.stop()


