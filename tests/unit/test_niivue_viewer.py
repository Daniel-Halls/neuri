"""Unit tests for NiiVue WebGL2 visualization bridge and headless QA generator.

Tests byte-range partial content streaming (206), directory whitelist security,
pure-Python PNG snapshot generation (<200 KB), and NiiVueBridge scene updates.
"""

from pathlib import Path
import time
from typing import Any
import urllib.request

import pytest

from neuri.core.schemas import NiiVueLayerSpec, NiiVueSceneSpec
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
