"""Localhost and remote SSH filesystem explorer and dialog bridge for NiiVue.

Provides directory inspection, neuroimaging volume detection, zero-daemon
remote SSH directory listing and volume staging, and platform-native file
dialog integration for selecting volumes.
"""

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from neuri.core.config import load_config
from neuri.remote.monitor import RemoteHostMonitor
from neuri.remote.ssh_pool import SSHControlMasterPool


class LocalFileExplorer:
    """Filesystem explorer for localhost and remote SSH hosts.

    Parameters
    ------------
    default_dir: Path | None
        Default workspace directory. Defaults to None (current working directory).
    cache_root: Path | None
        Local directory for staging remote volumes. Defaults to None.

    Returns
    --------
        LocalFileExplorer: LocalFileExplorer instance
            Constructed explorer instance.
    """

    VOLUME_EXTENSIONS: tuple[str, ...] = (
        ".nii",
        ".nii.gz",
        ".mgh",
        ".mgz",
        ".dcm",
        ".dim",
        ".img",
        ".hdr",
    )

    def __init__(
        self,
        default_dir: Path | None = None,
        cache_root: Path | None = None,
    ) -> None:
        """Initialize LocalFileExplorer with a root and staging cache directory.

        Parameters
        ------------
        default_dir: Path | None
            Default base directory. Defaults to None.
        cache_root: Path | None
            Directory used for staging remote SSH volumes. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes explorer instance.
        """
        self._default_dir: Path = (
            default_dir.resolve() if default_dir else Path.cwd().resolve()
        )
        default_cache: Path = (
            Path(tempfile.gettempdir()) / "neuri_viewer_cache"
        )
        self._cache_root: Path = (
            cache_root.resolve() if cache_root else default_cache
        )

    def is_volume_file(self, filename: str) -> bool:
        """Determine whether a filename corresponds to a supported volume.

        Parameters
        ------------
        filename: str
            Filename or file path string.

        Returns
        --------
            bool: boolean object
                True if filename matches a known neuroimaging volume extension.
        """
        lower_name: str = filename.lower()
        is_vol: bool = any(
            lower_name.endswith(ext) for ext in self.VOLUME_EXTENSIONS
        )
        return is_vol

    def format_file_size(self, size_bytes: int) -> str:
        """Format a byte count into a human-readable size string.

        Parameters
        ------------
        size_bytes: int
            Raw size in bytes.

        Returns
        --------
            str: string object
                Human-readable string (e.g. '12.4 MB', '450 KB').
        """
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            kb_val: float = size_bytes / 1024.0
            return f"{kb_val:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            mb_val: float = size_bytes / (1024.0 * 1024.0)
            return f"{mb_val:.1f} MB"
        gb_val: float = size_bytes / (1024.0 * 1024.0 * 1024.0)
        return f"{gb_val:.2f} GB"

    def get_available_hosts(self) -> dict[str, Any]:
        """Discover localhost and configured remote SSH hosts.

        Parameters
        ------------
        None

        Returns
        --------
            dict[str, Any]: dictionary object
                Dictionary with 'default_host' and 'hosts' list.
        """
        hosts: list[str] = ["localhost"]
        default_host: str = "localhost"

        try:
            cfg = load_config()
            if cfg.project.default_remote_host:
                default_host = cfg.project.default_remote_host
                if default_host not in hosts:
                    hosts.append(default_host)
            extra_hosts: dict[str, Any] = getattr(cfg, "remote_hosts", {})
            for host_key in extra_hosts:
                if host_key and host_key not in hosts:
                    hosts.append(host_key)
        except Exception:
            pass

        try:
            monitor: RemoteHostMonitor = RemoteHostMonitor()
            for mon_host in monitor.get_configured_hosts():
                if mon_host and mon_host not in hosts:
                    hosts.append(mon_host)
        except Exception:
            pass

        for ssh_host in self._parse_ssh_config_hosts():
            if ssh_host not in hosts:
                hosts.append(ssh_host)

        result: dict[str, Any] = {
            "default_host": default_host,
            "hosts": hosts,
        }
        return result

    def _parse_ssh_config_hosts(self) -> list[str]:
        """Parse non-wildcard Host aliases from ~/.ssh/config.

        Parameters
        ------------
        None

        Returns
        --------
            list[str]: list of string objects
                Discovered SSH host aliases.
        """
        ssh_config: Path = Path.home() / ".ssh" / "config"
        discovered: list[str] = []
        try:
            if not ssh_config.is_file():
                return discovered
            content: str = ssh_config.read_text(encoding="utf-8")
            for raw_line in content.splitlines():
                line: str = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.lower().startswith("host "):
                    aliases: list[str] = line[5:].split()
                    for alias in aliases:
                        if (
                            "*" not in alias
                            and "?" not in alias
                            and "!" not in alias
                            and alias not in ("localhost", "127.0.0.1")
                            and alias not in discovered
                        ):
                            discovered.append(alias)
        except OSError:
            pass
        return discovered

    def get_directory_entries(
        self, target_dir: Path
    ) -> list[dict[str, Any]]:
        """Scan a local directory and return sorted, classified metadata entries.

        Parameters
        ------------
        target_dir: Path
            Directory path to inspect.

        Returns
        --------
            list[dict[str, Any]]: list of dictionary objects
                Sorted list containing folder and volume file records.
        """
        entries: list[dict[str, Any]] = []
        try:
            with os.scandir(target_dir) as it:
                for item in it:
                    try:
                        is_dir: bool = item.is_dir(follow_symlinks=True)
                        is_vol: bool = False
                        size_bytes: int = 0
                        size_str: str = ""
                        mod_time: str = ""

                        if not is_dir:
                            is_vol = self.is_volume_file(item.name)
                            stat_res = item.stat()
                            size_bytes = stat_res.st_size
                            size_str = self.format_file_size(size_bytes)
                            dt: datetime = datetime.fromtimestamp(
                                stat_res.st_mtime, tz=UTC
                            )
                            mod_time = dt.strftime("%Y-%m-%d %H:%M")

                        record: dict[str, Any] = {
                            "name": item.name,
                            "path": str(Path(item.path).resolve()),
                            "is_dir": is_dir,
                            "is_volume": is_vol,
                            "size_bytes": size_bytes,
                            "size_formatted": size_str,
                            "modified": mod_time,
                        }
                        entries.append(record)
                    except OSError:
                        continue
        except OSError:
            return []

        def sort_key(rec: dict[str, Any]) -> tuple[int, int, str]:
            dir_rank: int = 0 if rec["is_dir"] else 1
            vol_rank: int = 0 if rec["is_volume"] else 1
            name_lower: str = rec["name"].lower()
            return (dir_rank, vol_rank, name_lower)

        entries.sort(key=sort_key)
        return entries

    def list_directory(
        self, dir_path: str | None = None, host: str = "localhost"
    ) -> dict[str, Any]:
        """List contents of a local or remote SSH directory with volume tagging.

        Parameters
        ------------
        dir_path: str | None
            Directory path to list. Defaults to None.
        host: str
            Target host identifier ('localhost' or SSH alias). Defaults to 'localhost'.

        Returns
        --------
            dict[str, Any]: dictionary object
                Payload containing host, path metadata, and sorted directory entries.
        """
        clean_host: str = (host or "localhost").strip()
        if clean_host not in ("localhost", "127.0.0.1"):
            return self._list_remote_directory(
                host=clean_host, dir_path=dir_path
            )

        resolved: Path
        if not dir_path or not dir_path.strip():
            resolved = self._default_dir
        else:
            expanded_str: str = os.path.expanduser(dir_path.strip())
            resolved = Path(expanded_str).resolve()

        if not resolved.exists() or not resolved.is_dir():
            resolved = self._default_dir

        entries: list[dict[str, Any]] = self.get_directory_entries(resolved)
        parent_path: str | None = None
        if resolved.parent != resolved:
            parent_path = str(resolved.parent)

        home_dir: str = str(Path.home())
        workspace_dir: str = str(self._default_dir)

        payload: dict[str, Any] = {
            "host": "localhost",
            "current_path": str(resolved),
            "parent_path": parent_path,
            "home_path": home_dir,
            "workspace_path": workspace_dir,
            "entries": entries,
        }
        return payload

    def _build_remote_list_script(self, target_dir_str: str) -> str:
        """Build a self-contained Python one-liner for remote directory listing.

        Parameters
        ------------
        target_dir_str: str
            Remote directory path string to inspect.

        Returns
        --------
            str: string object
                Python code string to execute via python3 -c on the remote host.
        """
        exts_json: str = json.dumps(list(self.VOLUME_EXTENSIONS))
        path_json: str = json.dumps(target_dir_str)
        script: str = (
            "import json, os\n"
            "from datetime import datetime, timezone\n"
            "from pathlib import Path\n"
            f"exts = tuple({exts_json})\n"
            f"req = {path_json}\n"
            "home = str(Path.home())\n"
            "cwd = str(Path.cwd())\n"
            "p = Path(os.path.expanduser(req)).resolve() if req else Path.home()\n"
            "if not p.exists() or not p.is_dir():\n"
            "    p = Path.home()\n"
            "def fmt(b):\n"
            "    if b < 1024: return f'{b} B'\n"
            "    if b < 1048576: return f'{b/1024.0:.1f} KB'\n"
            "    if b < 1073741824: return f'{b/1048576.0:.1f} MB'\n"
            "    return f'{b/1073741824.0:.2f} GB'\n"
            "entries = []\n"
            "try:\n"
            "    for item in os.scandir(p):\n"
            "        try:\n"
            "            is_d = item.is_dir(follow_symlinks=True)\n"
            "            is_v = False\n"
            "            sb = 0\n"
            "            sf = ''\n"
            "            mt = ''\n"
            "            if not is_d:\n"
            "                ln = item.name.lower()\n"
            "                is_v = any(ln.endswith(x) for x in exts)\n"
            "                st = item.stat()\n"
            "                sb = st.st_size\n"
            "                sf = fmt(sb)\n"
            "                dt = datetime.fromtimestamp(\n"
            "                    st.st_mtime, tz=timezone.utc\n"
            "                )\n"
            "                mt = dt.strftime('%Y-%m-%d %H:%M')\n"
            "            entries.append({\n"
            "                'name': item.name,\n"
            "                'path': str(Path(item.path).resolve()),\n"
            "                'is_dir': is_d,\n"
            "                'is_volume': is_v,\n"
            "                'size_bytes': sb,\n"
            "                'size_formatted': sf,\n"
            "                'modified': mt,\n"
            "            })\n"
            "        except OSError:\n"
            "            continue\n"
            "except OSError:\n"
            "    pass\n"
            "entries.sort(key=lambda r: (\n"
            "    0 if r['is_dir'] else 1,\n"
            "    0 if r['is_volume'] else 1,\n"
            "    r['name'].lower()\n"
            "))\n"
            "parent = str(p.parent) if p.parent != p else None\n"
            "print(json.dumps({\n"
            "    'current_path': str(p),\n"
            "    'parent_path': parent,\n"
            "    'home_path': home,\n"
            "    'workspace_path': cwd,\n"
            "    'entries': entries,\n"
            "}))\n"
        )
        return script

    def _list_remote_directory(
        self, host: str, dir_path: str | None = None
    ) -> dict[str, Any]:
        """List directory contents on a remote host over multiplexed SSH.

        Parameters
        ------------
        host: str
            Remote SSH host alias or user@hostname.
        dir_path: str | None
            Remote directory path to inspect. Defaults to None (remote home).

        Returns
        --------
            dict[str, Any]: dictionary object
                Directory listing dictionary from the remote host.
        """
        target_str: str = (dir_path or "").strip()
        py_script: str = self._build_remote_list_script(target_str)
        remote_cmd: str = f"python3 -c {shlex.quote(py_script)}"

        pool: SSHControlMasterPool = SSHControlMasterPool()
        ssh_cmd: list[str] = [*pool.build_ssh_args(host), remote_cmd]

        try:
            proc = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=20,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                data: dict[str, Any] = json.loads(proc.stdout.strip())
                data["host"] = host
                return data
            err_msg: str = (
                proc.stderr.strip() or f"SSH exited with code {proc.returncode}"
            )
        except Exception as exc:
            err_msg = str(exc)

        fallback: dict[str, Any] = {
            "host": host,
            "current_path": target_str or "~",
            "parent_path": None,
            "home_path": "~",
            "workspace_path": "~",
            "entries": [],
            "error": f"Remote SSH listing failed on '{host}': {err_msg}",
        }
        return fallback

    def stage_remote_volume(self, host: str, remote_path: str) -> Path:
        """Stage a neuroimaging volume from a remote SSH host to local cache.

        Parameters
        ------------
        host: str
            Remote SSH host alias or user@hostname.
        remote_path: str
            Absolute path to volume file on the remote host.

        Returns
        --------
            Path: Path object
                Local filesystem path to the staged volume file.
        """
        safe_host: str = re.sub(r"[^A-Za-z0-9._-]", "_", host)
        host_cache_dir: Path = self._cache_root / safe_host
        host_cache_dir.mkdir(parents=True, exist_ok=True)

        path_hash: str = hashlib.sha256(
            remote_path.encode("utf-8")
        ).hexdigest()[:12]
        base_name: str = os.path.basename(remote_path.rstrip("/"))
        if not base_name:
            base_name = "volume.nii.gz"

        staged_file: Path = host_cache_dir / f"{path_hash}_{base_name}"
        if staged_file.is_file() and staged_file.stat().st_size > 0:
            return staged_file

        pool: SSHControlMasterPool = SSHControlMasterPool()
        remote_cmd: str = f"cat {shlex.quote(remote_path)}"
        ssh_cmd: list[str] = [*pool.build_ssh_args(host), remote_cmd]

        tmp_target: Path = host_cache_dir / f".tmp_{path_hash}_{base_name}"
        with tmp_target.open("wb") as out_f:
            proc = subprocess.run(
                ssh_cmd,
                stdout=out_f,
                stderr=subprocess.PIPE,
                timeout=300,
            )

        if (
            proc.returncode != 0
            or not tmp_target.is_file()
            or tmp_target.stat().st_size == 0
        ):
            if tmp_target.exists():
                tmp_target.unlink()
            err_detail: str = proc.stderr.decode(
                "utf-8", errors="replace"
            ).strip()
            raise FileNotFoundError(
                f"Failed to fetch remote volume '{remote_path}' from "
                f"'{host}': {err_detail or 'empty or missing file'}"
            )

        tmp_target.replace(staged_file)
        return staged_file

    def pick_file_dialog(self) -> dict[str, Any]:
        """Trigger native host OS file explorer to select a volume.

        Parameters
        ------------
        None

        Returns
        --------
            dict[str, Any]: dictionary object
                Outcome containing status ('ok', 'canceled', 'unsupported') and path.
        """
        if sys.platform == "darwin":
            return self._pick_file_macos()
        elif sys.platform.startswith("linux"):
            return self._pick_file_linux()
        elif sys.platform in ("win32", "cygwin"):
            return self._pick_file_windows()
        return self._pick_file_tkinter()

    def _pick_file_macos(self) -> dict[str, Any]:
        """Open native macOS Finder file selection dialog using osascript.

        Parameters
        ------------
        None

        Returns
        --------
            dict[str, Any]: dictionary object
                Outcome containing status and selected POSIX path.
        """
        if not shutil.which("osascript"):
            return self._pick_file_tkinter()

        apple_script: str = (
            'tell application (path to frontmost application as text)\n'
            '    set theFile to choose file with prompt '
            '"Select Neuroimaging Volume (.nii, .nii.gz, .mgz, .dcm)"\n'
            'end tell\n'
            'POSIX path of theFile'
        )
        try:
            res = subprocess.run(
                ["osascript", "-e", apple_script],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if res.returncode == 0:
                selected_path: str = res.stdout.strip()
                if selected_path and Path(selected_path).is_file():
                    return {"status": "ok", "path": selected_path}
            if "User canceled" in res.stderr or res.returncode != 0:
                return {"status": "canceled"}
        except subprocess.TimeoutExpired:
            return {"status": "canceled", "message": "Dialog timed out"}
        except Exception as err:
            return {
                "status": "unsupported",
                "message": f"macOS dialog error: {err}",
            }
        return {"status": "canceled"}

    def _pick_file_linux(self) -> dict[str, Any]:
        """Open native Linux file selection dialog using zenity, kdialog, or tkinter.

        Parameters
        ------------
        None

        Returns
        --------
            dict[str, Any]: dictionary object
                Outcome containing status and selected path.
        """
        if shutil.which("zenity"):
            try:
                cmd = [
                    "zenity",
                    "--file-selection",
                    "--title=Select Neuroimaging Volume",
                    (
                        "--file-filter=Neuroimaging Volumes | "
                        "*.nii *.nii.gz *.mgh *.mgz *.dcm *.dim *.img *.hdr"
                    ),
                    "--file-filter=All Files | *",
                ]
                res = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=120
                )
                if res.returncode == 0:
                    selected_path = res.stdout.strip()
                    if selected_path and Path(selected_path).is_file():
                        return {"status": "ok", "path": selected_path}
                return {"status": "canceled"}
            except Exception:
                pass

        if shutil.which("kdialog"):
            try:
                cmd = [
                    "kdialog",
                    "--getopenfilename",
                    str(self._default_dir),
                    "*.nii *.nii.gz *.mgh *.mgz *.dcm|Neuroimaging Volumes",
                ]
                res = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=120
                )
                if res.returncode == 0:
                    selected_path = res.stdout.strip()
                    if selected_path and Path(selected_path).is_file():
                        return {"status": "ok", "path": selected_path}
                return {"status": "canceled"}
            except Exception:
                pass

        return self._pick_file_tkinter()

    def _pick_file_windows(self) -> dict[str, Any]:
        """Open native Windows file selection dialog.

        Parameters
        ------------
        None

        Returns
        --------
            dict[str, Any]: dictionary object
                Outcome containing status and selected path.
        """
        return self._pick_file_tkinter()

    def _pick_file_tkinter(self) -> dict[str, Any]:
        """Fallback file selection dialog using Tkinter.

        Parameters
        ------------
        None

        Returns
        --------
            dict[str, Any]: dictionary object
                Outcome containing status and selected path.
        """
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            selected_path: str = filedialog.askopenfilename(
                title="Select Neuroimaging Volume",
                initialdir=str(self._default_dir),
                filetypes=[
                    (
                        "Neuroimaging Volumes",
                        "*.nii;*.nii.gz;*.mgh;*.mgz;*.dcm;*.dim;*.img;*.hdr",
                    ),
                    ("All Files", "*.*"),
                ],
            )
            root.destroy()
            if selected_path and Path(selected_path).is_file():
                return {"status": "ok", "path": selected_path}
            return {"status": "canceled"}
        except Exception as err:
            return {
                "status": "unsupported",
                "message": f"GUI file dialog unavailable: {err}",
            }


__all__: list[str] = ["LocalFileExplorer"]
