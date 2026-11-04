"""Desktop sidecar process entrypoint for Neuri Studio GUI and Tauri v2.

Binds an ephemeral loopback HTTP server, prints the handshake URL to stdout
for the Tauri Rust supervisor, monitors parent process lifecycle, and enables
real-time asset hot-reloading in development mode.
"""

import argparse
import os
from pathlib import Path
import sys
import threading
import time
from typing import Any

from neuri.core.blackboard import Blackboard
from neuri.core.schemas import SessionEventType
from neuri.core.session import NeuriSessionEngine
from neuri.gui.hot_reload import NeuriHotReloader
from neuri.gui.server import NeuriGUIServer, resolve_gui_static_dir
from neuri.ui.history import PromptHistoryManager
from neuri.ui.theme import NeuriThemeManager


class NeuriSidecarRunner:
    """Encapsulates sidecar process lifecycle, server, and watchdog threads.

    Parameters
    ------------
    workspace_dir: Path
        Target workspace filesystem directory.
    model: str | None
        Optional model override. Defaults to None.
    harness: str | None
        Optional harness override. Defaults to None.
    port: int
        HTTP bind port. Defaults to 0 (ephemeral auto-assignment).
    is_dev: bool
        Whether development mode hot-reloading is active. Defaults to False.

    Returns
    --------
        NeuriSidecarRunner: NeuriSidecarRunner instance
            Constructed sidecar runner.
    """

    def __init__(
        self,
        workspace_dir: Path,
        model: str | None = None,
        harness: str | None = None,
        port: int = 0,
        is_dev: bool = False,
    ) -> None:
        """Initialize sidecar runner configuration and synchronization primitives.

        Parameters
        ------------
        workspace_dir: Path
            Directory for session execution and state tracking.
        model: str | None
            Model name string. Defaults to None.
        harness: str | None
            Harness identifier string. Defaults to None.
        port: int
            Preferred TCP port (0 for ephemeral). Defaults to 0.
        is_dev: bool
            Flag enabling dev-mode filesystem watchers. Defaults to False.

        Returns
        --------
            None: NoneType object
                Initializes runner state.
        """
        self.workspace_dir: Path = workspace_dir.resolve()
        self.model: str | None = model
        self.harness: str | None = harness
        self.port: int = port
        self.is_dev: bool = is_dev

        self._shutdown_event: threading.Event = threading.Event()
        self._server: NeuriGUIServer | None = None
        self._server_thread: threading.Thread | None = None
        self._hot_reloader: NeuriHotReloader | None = None
        self._bound_port: int = 0
        self._parent_pid: int = os.getppid()

    @property
    def bound_port(self) -> int:
        """Return actual TCP port assigned by operating system.

        Parameters
        ------------
        None

        Returns
        --------
            int: integer object
                Assigned TCP port number.
        """
        return self._bound_port

    def run(self) -> int:
        """Run the sidecar server, output handshake, and block until shutdown.

        Parameters
        ------------
        None

        Returns
        --------
            int: integer object
                Process exit status code.
        """
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        db_path: Path = self.workspace_dir / ".neuri" / "state.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        blackboard: Blackboard = Blackboard(db_path)
        session_engine: NeuriSessionEngine = NeuriSessionEngine(
            workspace_dir=self.workspace_dir,
            model=self.model,
            harness=self.harness,
            blackboard=blackboard,
        )
        theme_manager: NeuriThemeManager = NeuriThemeManager(
            workspace_dir=self.workspace_dir
        )
        history_path: Path = self.workspace_dir / ".neuri" / "history"
        history_manager: PromptHistoryManager = PromptHistoryManager(
            history_file=history_path
        )

        static_dir: Path = resolve_gui_static_dir()
        server: NeuriGUIServer = NeuriGUIServer(
            server_address=("127.0.0.1", self.port),
            session_engine=session_engine,
            theme_manager=theme_manager,
            history_manager=history_manager,
            static_dir=static_dir,
        )
        self._server = server
        self._bound_port = int(server.server_address[1])

        # Start HTTP server in daemon thread
        self._server_thread = threading.Thread(
            target=server.serve_forever,
            name="neuri-sidecar-http",
            daemon=True,
        )
        self._server_thread.start()

        # Emit standard handshake line for Tauri Rust supervisor
        handshake_url: str = f"http://127.0.0.1:{self._bound_port}"
        sys.stdout.write(f"NEURI_STUDIO_READY {handshake_url}\n")
        sys.stdout.flush()

        # Start parent-PID and stdin EOF watchdog
        self._start_watchdog()

        # Start hot reload watcher if in dev mode
        if self.is_dev:
            self._start_hot_reload(session_engine, static_dir)

        # Block until shutdown signal received
        self._shutdown_event.wait()
        self.stop()
        return 0

    def _start_watchdog(self) -> None:
        """Spawn daemon thread to monitor stdin EOF and parent process survival.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Starts watchdog monitoring thread.
        """
        watchdog_thread: threading.Thread = threading.Thread(
            target=self._watchdog_loop,
            name="neuri-sidecar-watchdog",
            daemon=True,
        )
        watchdog_thread.start()

    def _watchdog_loop(self) -> None:
        """Monitor stdin read for EOF and check if parent PID changed.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Loops until parent process terminates.
        """

        def _stdin_reader() -> None:
            """Read standard input and signal shutdown upon receiving EOF.

            Parameters
            ------------
            None

            Returns
            --------
                None: NoneType object
                    Signals shutdown on EOF.
            """
            try:
                while not self._shutdown_event.is_set():
                    line: str = sys.stdin.readline()
                    if not line:
                        self._shutdown_event.set()
                        break
            except Exception:
                self._shutdown_event.set()

        stdin_thread: threading.Thread = threading.Thread(
            target=_stdin_reader,
            name="neuri-stdin-reader",
            daemon=True,
        )
        stdin_thread.start()

        # Poll parent PID (if parent dies on POSIX, ppid changes to init / 1)
        while not self._shutdown_event.is_set():
            time.sleep(1.0)
            try:
                curr_ppid: int = os.getppid()
                if curr_ppid != self._parent_pid:
                    self._shutdown_event.set()
                    break
            except OSError:
                self._shutdown_event.set()
                break

    def _start_hot_reload(
        self, session_engine: NeuriSessionEngine, static_dir: Path
    ) -> None:
        """Start file watcher to emit SSE reload events on static asset changes.

        Parameters
        ------------
        session_engine: NeuriSessionEngine
            Session engine instance for emitting events.
        static_dir: Path
            Directory containing GUI static assets.

        Returns
        --------
            None: NoneType object
                Initializes and starts hot reloader.
        """
        viewer_static: Path = (
            static_dir.parent.parent / "viewer" / "static"
        ).resolve()
        watch_dirs: list[Path] = [static_dir]
        if viewer_static.is_dir():
            watch_dirs.append(viewer_static)

        code_dir: Path = static_dir.parent.parent.resolve()

        def _on_asset_changed(path: Path) -> None:
            """Emit live asset reload SSE event to connected GUI clients.

            Parameters
            ------------
            path: Path
                Modified static asset filesystem path.

            Returns
            --------
                None: NoneType object
                    Dispatches SSE reload payload.
            """
            try:
                rel_str: str = str(path.name)
                session_engine.emit_event(
                    event_type=SessionEventType.STATUS_UPDATE,
                    payload={
                        "action": "live_reload_assets",
                        "path": rel_str,
                    },
                )
            except Exception:
                pass

        self._hot_reloader = NeuriHotReloader(
            static_dirs=watch_dirs,
            code_dirs=[code_dir],
            on_asset_changed=_on_asset_changed,
            poll_interval=0.5,
        )
        self._hot_reloader.start()

    def stop(self) -> None:
        """Cleanly terminate HTTP server, hot reloader, and background threads.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Shuts down server and cleanup routines.
        """
        self._shutdown_event.set()
        if self._hot_reloader is not None:
            self._hot_reloader.stop()
            self._hot_reloader = None

        if self._server is not None:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:
                pass
            self._server = None


def main() -> None:
    """Parse command line flags and execute Neuri sidecar server process.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Executes runner and exits with status code.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Neuri Studio Desktop Sidecar Process"
    )
    parser.add_argument(
        "--workspace",
        "-w",
        type=Path,
        default=Path.cwd(),
        help="Workspace directory",
    )
    parser.add_argument(
        "--model",
        "-m",
        type=str,
        default=None,
        help="AI model override",
    )
    parser.add_argument(
        "--harness",
        "-H",
        type=str,
        default=None,
        help="AI harness override",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=0,
        help="Port number (0 for ephemeral auto-binding)",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Enable development mode with live filesystem watchers",
    )

    args = parser.parse_args()
    runner: NeuriSidecarRunner = NeuriSidecarRunner(
        workspace_dir=args.workspace,
        model=args.model,
        harness=args.harness,
        port=args.port,
        is_dev=args.dev,
    )
    exit_code: int = runner.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
