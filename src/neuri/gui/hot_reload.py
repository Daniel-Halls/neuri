"""Development hot-reload watcher for Neuri Studio GUI and Python sidecar.

Monitors static UI assets (HTML, CSS, JS) and Python source files to trigger
live browser reload events and graceful worker restarts during active development.
"""

from collections.abc import Callable
from pathlib import Path
import threading
import time
from typing import Any


class NeuriHotReloader:
    """Monitors filesystem changes across GUI static assets and Python source.

    Parameters
    ------------
    static_dirs: list[Path]
        Directories containing static web assets (HTML/CSS/JS).
    code_dirs: list[Path] | None
        Optional directories containing Python source code to monitor.
    on_asset_changed: Callable[[Path], None] | None
        Callback executed when a static asset file is modified.
    on_code_changed: Callable[[Path], None] | None
        Callback executed when a Python file is modified.
    poll_interval: float
        Polling interval in seconds. Defaults to 0.4.

    Returns
    --------
        NeuriHotReloader: NeuriHotReloader instance
            Constructed filesystem hot-reload monitor.
    """

    def __init__(
        self,
        static_dirs: list[Path],
        code_dirs: list[Path] | None = None,
        on_asset_changed: Callable[[Path], None] | None = None,
        on_code_changed: Callable[[Path], None] | None = None,
        poll_interval: float = 0.4,
    ) -> None:
        """Initialize hot reload watcher state and file timestamp caches.

        Parameters
        ------------
        static_dirs: list[Path]
            Directories containing web assets to watch.
        code_dirs: list[Path] | None
            Directories containing Python source files. Defaults to None.
        on_asset_changed: Callable[[Path], None] | None
            Asset change callback. Defaults to None.
        on_code_changed: Callable[[Path], None] | None
            Python code change callback. Defaults to None.
        poll_interval: float
            Interval between timestamp sweeps. Defaults to 0.4.

        Returns
        --------
            None: NoneType object
                Initializes watcher instance.
        """
        self._static_dirs: list[Path] = [
            d.resolve() for d in static_dirs if d.is_dir()
        ]
        self._code_dirs: list[Path] = (
            [d.resolve() for d in code_dirs if d.is_dir()]
            if code_dirs is not None
            else []
        )
        self._on_asset_changed: Callable[[Path], None] | None = on_asset_changed
        self._on_code_changed: Callable[[Path], None] | None = on_code_changed
        self._poll_interval: float = poll_interval

        self._asset_mtimes: dict[Path, float] = {}
        self._code_mtimes: dict[Path, float] = {}
        self._is_running: bool = False
        self._thread: threading.Thread | None = None

        self._snapshot_timestamps()

    def _snapshot_timestamps(self) -> None:
        """Populate initial baseline modification timestamps across target trees.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Populates internal timestamp dictionaries.
        """
        self._asset_mtimes = self._scan_dirs(
            self._static_dirs, (".html", ".css", ".js", ".svg", ".json")
        )
        self._code_mtimes = self._scan_dirs(self._code_dirs, (".py", ".yaml"))

    def _scan_dirs(
        self, dirs: list[Path], extensions: tuple[str, ...]
    ) -> dict[Path, float]:
        """Scan directories and return map of file paths to modification times.

        Parameters
        ------------
        dirs: list[Path]
            Directory list to scan recursively.
        extensions: tuple[str, ...]
            File extension filter tuple.

        Returns
        --------
            dict[Path, float]: dictionary object
                Mapping from Path to float epoch modification timestamp.
        """
        mtimes: dict[Path, float] = {}
        for directory in dirs:
            if not directory.is_dir():
                continue
            for p in directory.rglob("*"):
                if p.is_file() and p.suffix.lower() in extensions:
                    try:
                        mtimes[p] = p.stat().st_mtime
                    except OSError:
                        continue
        return mtimes

    def start(self) -> None:
        """Start background polling thread if not currently running.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Spawns daemon watcher thread.
        """
        if self._is_running:
            return
        self._is_running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            name="neuri-hot-reload-watcher",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop background polling thread and wait for termination.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Stops thread execution.
        """
        self._is_running = False
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)
            self._thread = None

    def _run_loop(self) -> None:
        """Execute continuous polling loop comparing file modification times.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Runs polling sweeps until stopped.
        """
        while self._is_running:
            time.sleep(self._poll_interval)
            try:
                self._check_assets()
                self._check_code()
            except Exception:
                continue

    def _check_assets(self) -> None:
        """Check static asset files for additions, deletions, or updates.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Executes callback on detected asset modifications.
        """
        current: dict[Path, float] = self._scan_dirs(
            self._static_dirs, (".html", ".css", ".js", ".svg", ".json")
        )
        changed_file: Path | None = None

        for path, mtime in current.items():
            prev_mtime = self._asset_mtimes.get(path)
            if prev_mtime is None or mtime > prev_mtime:
                changed_file = path
                break

        if changed_file is None:
            # Check for deleted files
            deleted = set(self._asset_mtimes.keys()) - set(current.keys())
            if deleted:
                changed_file = next(iter(deleted))

        if changed_file is not None:
            self._asset_mtimes = current
            if self._on_asset_changed is not None:
                self._on_asset_changed(changed_file)

    def _check_code(self) -> None:
        """Check Python code files for modifications.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Executes callback on detected Python source modifications.
        """
        if not self._code_dirs or self._on_code_changed is None:
            return

        current: dict[Path, float] = self._scan_dirs(
            self._code_dirs, (".py", ".yaml")
        )
        changed_file: Path | None = None

        for path, mtime in current.items():
            prev_mtime = self._code_mtimes.get(path)
            if prev_mtime is None or mtime > prev_mtime:
                changed_file = path
                break

        if changed_file is not None:
            self._code_mtimes = current
            self._on_code_changed(changed_file)


__all__: list[str] = [
    "NeuriHotReloader",
]
