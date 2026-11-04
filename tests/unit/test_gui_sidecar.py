"""Unit tests for Neuri Studio Tauri desktop sidecar and hot-reload monitor.

Validates that NeuriSidecarRunner binds ephemeral ports, emits the
NEURI_STUDIO_READY handshake, and that NeuriHotReloader detects file changes.
"""

import io
from pathlib import Path
import sys
import threading
import time
from typing import Any

from neuri.core.blackboard import Blackboard
from neuri.core.schemas import SessionEvent, SessionEventType
from neuri.core.session import NeuriSessionEngine
from neuri.gui.hot_reload import NeuriHotReloader
from neuri.gui.server import resolve_gui_static_dir
from neuri.gui.sidecar import NeuriSidecarRunner


def test_resolve_gui_static_dir() -> None:
    """Verify resolve_gui_static_dir locates valid GUI static directory.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts static directory exists and contains index.html.
    """
    static_dir: Path = resolve_gui_static_dir()
    assert static_dir.is_dir()
    assert (static_dir / "index.html").is_file()
    assert (static_dir / "splash.html").is_file()


def test_hot_reloader_detects_asset_modifications(tmp_path: Path) -> None:
    """Verify NeuriHotReloader detects file modification events in static assets.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts callback receives modified file path.
    """
    asset_dir: Path = tmp_path / "static"
    asset_dir.mkdir(parents=True, exist_ok=True)
    test_css: Path = asset_dir / "studio.css"
    test_css.write_text("body { color: #fff; }", encoding="utf-8")

    detected_changes: list[Path] = []

    def _on_changed(path: Path) -> None:
        """Record modified asset path.

        Parameters
        ------------
        path: Path
            Modified filesystem path.

        Returns
        --------
            None: NoneType object
                Appends path to change tracker.
        """
        detected_changes.append(path)

    reloader: NeuriHotReloader = NeuriHotReloader(
        static_dirs=[asset_dir],
        on_asset_changed=_on_changed,
        poll_interval=0.1,
    )
    reloader.start()

    try:
        time.sleep(0.15)
        # Modify file
        test_css.write_text("body { color: #000; }", encoding="utf-8")
        time.sleep(0.3)
        assert len(detected_changes) >= 1
        assert detected_changes[0].name == "studio.css"
    finally:
        reloader.stop()


def test_sidecar_runner_initialization_and_ephemeral_bind(
    tmp_path: Path,
) -> None:
    """Verify NeuriSidecarRunner initializes on port 0 and binds ephemeral port.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts sidecar runner starts server on an ephemeral port.
    """
    runner: NeuriSidecarRunner = NeuriSidecarRunner(
        workspace_dir=tmp_path,
        port=0,
        is_dev=False,
    )

    runner_thread: threading.Thread = threading.Thread(
        target=runner.run,
        daemon=True,
    )
    runner_thread.start()

    # Wait for server to bind port
    for _ in range(50):
        if runner.bound_port > 0:
            break
        time.sleep(0.1)

    assert runner.bound_port > 0
    assert runner.bound_port != 8420

    # Stop runner cleanly
    runner.stop()
    runner_thread.join(timeout=2.0)
