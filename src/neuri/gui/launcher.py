"""Desktop application launcher and lifecycle controller for Neuri Studio.

Starts the background NeuriGUIServer and orchestrates display in a native
desktop window (via pywebview if available) or launches the system browser.
"""

import contextlib
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from typing import Any
import webbrowser

from neuri.core.paths import PathResolver
from neuri.core.session import NeuriSessionEngine
from neuri.gui.server import NeuriGUIServer
from neuri.ui.history import PromptHistoryManager
from neuri.ui.theme import NeuriThemeManager


def find_available_port(
    host: str = "127.0.0.1", start_port: int = 8420, max_attempts: int = 50
) -> int:
    """Find the first open TCP port beginning at start_port.

    Parameters
    ------------
    host: str
        Target binding host address. Defaults to "127.0.0.1".
    start_port: int
        Port number to test first. Defaults to 8420.
    max_attempts: int
        Maximum consecutive ports to test. Defaults to 50.

    Returns
    --------
        int: integer port number
            Available port for socket binding.
    """
    for candidate in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, candidate))
                return candidate
            except OSError:
                continue
    return start_port


class NeuriGUILauncher:
    """Orchestrates Neuri Studio server lifecycle and native window display.

    Parameters
    ------------
    workspace_dir: Path | None
        Target workspace root directory. Defaults to Path.cwd().
    model: str | None
        Optional model override. Defaults to None.
    harness: str | None
        Optional harness override. Defaults to None.
    port: int
        Preferred HTTP port. Defaults to 8420.
    open_browser: bool
        Whether to automatically open browser if pywebview is absent.
        Defaults to True.

    Returns
    --------
        NeuriGUILauncher: NeuriGUILauncher instance
            Constructed launcher manager.
    """

    def __init__(
        self,
        workspace_dir: Path | None = None,
        model: str | None = None,
        harness: str | None = None,
        port: int = 8420,
        open_browser: bool = True,
    ) -> None:
        """Initialize launcher with workspace configuration and preferred port.

        Parameters
        ------------
        workspace_dir: Path | None
            Workspace directory. Defaults to None.
        model: str | None
            Model override. Defaults to None.
        harness: str | None
            Harness override. Defaults to None.
        port: int
            Preferred port. Defaults to 8420.
        open_browser: bool
            Whether to open browser. Defaults to True.

        Returns
        --------
            None: NoneType object
                Initializes launcher attributes.
        """
        self._workspace_dir: Path = (
            workspace_dir.resolve() if workspace_dir else Path.cwd().resolve()
        )
        self._model: str | None = model
        self._harness: str | None = harness
        self._preferred_port: int = port
        self._open_browser: bool = open_browser
        self._server: NeuriGUIServer | None = None
        self._server_thread: threading.Thread | None = None
        self._port: int = port
        self._url: str = f"http://127.0.0.1:{port}"

    @property
    def url(self) -> str:
        """Active local HTTP URL for GUI server.

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                URL string.
        """
        active_url: str = self._url
        return active_url

    @property
    def workspace_dir(self) -> Path:
        """Active workspace root directory.

        Parameters
        ------------
        None

        Returns
        --------
            Path: Path object
                Workspace directory path.
        """
        active_ws: Path = self._workspace_dir
        return active_ws

    @property
    def model(self) -> str | None:
        """Active AI model override.

        Parameters
        ------------
        None

        Returns
        --------
            str | None: string or None
                Model identifier.
        """
        active_model: str | None = self._model
        return active_model

    @property
    def harness(self) -> str | None:
        """Active AI harness override.

        Parameters
        ------------
        None

        Returns
        --------
            str | None: string or None
                Harness identifier.
        """
        active_harness: str | None = self._harness
        return active_harness

    def start_server(self) -> str:
        """Instantiate and start NeuriGUIServer on a background daemon thread.

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                URL where Neuri Studio is running.
        """
        self._port = find_available_port(
            host="127.0.0.1", start_port=self._preferred_port
        )
        self._url = f"http://127.0.0.1:{self._port}"

        session_engine: NeuriSessionEngine = NeuriSessionEngine(
            workspace_dir=self._workspace_dir,
            model=self._model,
            harness=self._harness,
        )
        theme_manager: NeuriThemeManager = NeuriThemeManager(
            workspace_dir=self._workspace_dir
        )
        history_path: Path = self._workspace_dir / ".neuri" / "history"
        history_manager: PromptHistoryManager = PromptHistoryManager(
            history_file=history_path
        )
        static_dir: Path = Path(__file__).resolve().parent / "static"

        self._server = NeuriGUIServer(
            server_address=("127.0.0.1", self._port),
            session_engine=session_engine,
            theme_manager=theme_manager,
            history_manager=history_manager,
            static_dir=static_dir,
        )

        self._server_thread = threading.Thread(
            target=self._server.serve_forever, daemon=True
        )
        self._server_thread.start()
        return self._url

    def launch(self, web: bool = False) -> None:
        """Start and display GUI in native desktop window or fallback web browser.

        Parameters
        ------------
        web: bool
            Whether to force web browser mode instead of native desktop app.
            Defaults to False.

        Returns
        --------
            None: NoneType object
                Runs interactive loop until window closes or Ctrl+C.
        """
        if not web:
            try:
                self.launch_desktop()
                return
            except Exception as err:
                print(
                    f"[!] Desktop launch encountered: {err}. "
                    "Falling back to web browser...",
                    file=sys.stderr,
                )
        self.launch_browser()

    def launch_desktop(self) -> None:
        """Launch native standalone Tauri desktop window shell.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Spawns native desktop process and waits for termination.
        """
        repo_root: Path = PathResolver.get_repo_root()
        debug_bin: Path = (
            repo_root / "src-tauri" / "target" / "debug" / "neuri-desktop"
        )
        release_bin: Path = (
            repo_root / "src-tauri" / "target" / "release" / "neuri-desktop"
        )

        target_bin: Path | None = None
        if release_bin.is_file():
            target_bin = release_bin
        elif debug_bin.is_file():
            target_bin = debug_bin
        else:
            # Build debug binary on demand if cargo is available
            with contextlib.suppress(Exception):
                subprocess.run(
                    [
                        "cargo",
                        "build",
                        "--manifest-path",
                        str(repo_root / "src-tauri" / "Cargo.toml"),
                    ],
                    cwd=repo_root,
                    check=True,
                )
                if debug_bin.is_file():
                    target_bin = debug_bin

        if target_bin is not None and target_bin.is_file():
            desktop_args: list[str] = [str(target_bin)]
            if self.workspace_dir:
                desktop_args.extend(["--workspace", str(self.workspace_dir)])
            if self.model:
                desktop_args.extend(["--model", self.model])
            if self.harness:
                desktop_args.extend(["--harness", self.harness])
            subprocess.run(desktop_args, cwd=repo_root, check=True)
            return

        # Fallback to browser if no desktop binary is available
        self.launch_browser()

    def launch_browser(self) -> None:
        """Start server and display GUI in system browser.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Runs interactive loop until Ctrl+C.
        """
        url: str = self.start_server()

        # Check for pywebview native desktop window
        has_webview: bool = False
        webview_module: Any = None
        try:
            import webview

            has_webview = True
            webview_module = webview
        except ImportError:
            has_webview = False

        if has_webview and webview_module is not None:
            try:
                webview_module.create_window(
                    title="Neuri Studio",
                    url=url,
                    width=1440,
                    height=900,
                    min_size=(960, 600),
                )
                webview_module.start()
                self.stop()
                return
            except Exception:
                pass

        # Fallback: System browser app mode or tab
        if self._open_browser:
            with contextlib.suppress(Exception):
                webbrowser.open(url)

        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self) -> None:
        """Shut down the GUI HTTP server cleanly.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Stops server thread.
        """
        if self._server is not None:
            with contextlib.suppress(Exception):
                self._server.shutdown()
                self._server.server_close()
            self._server = None


__all__: list[str] = [
    "NeuriGUILauncher",
    "find_available_port",
]
