"""Automated build and packaging pipeline for Neuri Studio desktop application.

Executes PyInstaller sidecar freezing and Tauri v2 desktop compilation to produce
standalone native application bundles (.app on macOS, .msi on Windows, .AppImage on Linux).
"""

import argparse
from pathlib import Path
import platform
import shutil
import subprocess
import sys


class NeuriDesktopBuilder:
    """Orchestrates multi-stage freezing and Tauri packaging for desktop distribution.

    Parameters
    ------------
    repo_root: Path | None
        Repository root directory. Defaults to None (resolved automatically).

    Returns
    --------
        NeuriDesktopBuilder: NeuriDesktopBuilder instance
            Constructed builder instance.
    """

    def __init__(self, repo_root: Path | None = None) -> None:
        """Initialize desktop builder with repository root and binary paths.

        Parameters
        ------------
        repo_root: Path | None
            Repository root directory. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes builder state.
        """
        self.repo_root: Path = (
            repo_root.resolve()
            if repo_root is not None
            else Path(__file__).resolve().parent.parent
        )
        self.src_tauri_dir: Path = self.repo_root / "src-tauri"
        self.binaries_dir: Path = self.src_tauri_dir / "binaries"

    def get_host_target_triple(self) -> str:
        """Determine host target triple from rustc -vV output.

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                Target triple string (e.g. 'aarch64-apple-darwin').
        """
        try:
            res: subprocess.CompletedProcess[str] = subprocess.run(
                ["rustc", "-vV"],
                capture_output=True,
                text=True,
                check=True,
            )
            for line in res.stdout.splitlines():
                if line.startswith("host:"):
                    return line.split(":", 1)[1].strip()
        except Exception:
            pass

        # Fallback mapping
        machine: str = platform.machine().lower()
        system: str = platform.system().lower()
        if system == "darwin":
            arch: str = "aarch64" if machine in ("arm64", "aarch64") else "x86_64"
            return f"{arch}-apple-darwin"
        elif system == "linux":
            arch = "aarch64" if machine in ("arm64", "aarch64") else "x86_64"
            return f"{arch}-unknown-linux-gnu"
        elif system == "windows":
            return "x86_64-pc-windows-msvc"
        return "x86_64-apple-darwin"

    def freeze_python_sidecar(self, target_triple: str) -> Path:
        """Freeze Python engine sidecar using PyInstaller into src-tauri/binaries.

        Parameters
        ------------
        target_triple: str
            Host target triple string.

        Returns
        --------
            Path: Path object
                Path to frozen sidecar binary.
        """
        self.binaries_dir.mkdir(parents=True, exist_ok=True)
        binary_name: str = f"neuri-engine-{target_triple}"
        output_bin: Path = self.binaries_dir / binary_name

        sidecar_entry: Path = (
            self.repo_root / "src" / "neuri" / "gui" / "sidecar.py"
        )
        cmd: list[str] = [
            "uv",
            "run",
            "pyinstaller",
            "--noconfirm",
            "--clean",
            "--onefile",
            "--name",
            binary_name,
            "--distpath",
            str(self.binaries_dir),
            str(sidecar_entry),
        ]

        print(f">> Freezing Python sidecar: {' '.join(cmd)}")
        subprocess.run(cmd, cwd=self.repo_root, check=True)
        return output_bin

    def build_tauri_bundle(self, release: bool = True) -> int:
        """Execute Cargo or Tauri build to package native application bundle.

        Parameters
        ------------
        release: bool
            Whether to build in release mode. Defaults to True.

        Returns
        --------
            int: integer object
                Build process exit code.
        """
        target_triple: str = self.get_host_target_triple()
        print(f">> Detected target triple: {target_triple}")

        cargo_cmd: list[str] = [
            "cargo",
            "build",
            "--manifest-path",
            str(self.src_tauri_dir / "Cargo.toml"),
        ]
        if release:
            cargo_cmd.append("--release")

        print(f">> Building Tauri desktop binary: {' '.join(cargo_cmd)}")
        res: subprocess.CompletedProcess[Any] = subprocess.run(
            cargo_cmd, cwd=self.repo_root
        )
        return res.returncode


def main() -> None:
    """Parse build flags and run Neuri desktop application packaging.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Executes builder and exits.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Neuri Studio Desktop Application Packager"
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Build in development debug mode instead of release.",
    )
    parser.add_argument(
        "--freeze-only",
        action="store_true",
        help="Only freeze Python sidecar without building Tauri app.",
    )
    args = parser.parse_args()

    builder: NeuriDesktopBuilder = NeuriDesktopBuilder()
    if args.freeze_only:
        triple: str = builder.get_host_target_triple()
        builder.freeze_python_sidecar(triple)
        sys.exit(0)

    code: int = builder.build_tauri_bundle(release=not args.dev)
    sys.exit(code)


if __name__ == "__main__":
    main()
