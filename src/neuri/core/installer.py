"""Neuri environment installer and home directory bootstrapping manager.

Installs and synchronizes base assets from the repository 'neuri' base directory
into $HOME/.neuri/ containing global/, skills/, mcp/, and rules/.
"""

from pathlib import Path
import shutil
from typing import Any

from neuri.core.paths import PathResolver


class NeuriInstaller:
    """Installs Neuri base configuration, skills, MCP, and master prompt into ~/.neuri.

    Parameters
    ------------
    target_dir: Path | None
        Target directory for installation. Defaults to Path.home() / ".neuri".
    source_dir: Path | None
        Source template directory. Defaults to PathResolver.get_base_template_dir().

    Returns
    --------
        NeuriInstaller: NeuriInstaller instance
            Constructed installer instance.
    """

    DEFAULT_INSTALL_DIRNAME: str = ".neuri"

    def __init__(
        self,
        target_dir: Path | None = None,
        source_dir: Path | None = None,
    ) -> None:
        """Initialize installer with target and source directory paths.

        Parameters
        ------------
        target_dir: Path | None
            Installation target directory. Defaults to ~/.neuri.
        source_dir: Path | None
            Source template directory. Defaults to repo root 'neuri'.

        Returns
        --------
            None: NoneType object
                Initializes directory paths.
        """
        self._target_dir: Path = (
            target_dir
            if target_dir is not None
            else Path.home() / self.DEFAULT_INSTALL_DIRNAME
        )
        self._source_dir: Path = (
            source_dir
            if source_dir is not None
            else PathResolver.get_base_template_dir()
        )

    def install(self, force: bool = False) -> dict[str, Any]:
        """Install base global, skills, mcp, and rules folders into target.

        Parameters
        ------------
        force: bool
            Whether to overwrite existing files. Defaults to False.

        Returns
        --------
            dict[str, Any]: dictionary object
                Summary dictionary of installed directories and files.
        """
        self._target_dir.mkdir(parents=True, exist_ok=True)

        installed_sections: list[str] = [
            "global",
            "skills",
            "mcp",
            "rules",
            "themes",
        ]
        result_paths: dict[str, Any] = {
            "target_dir": str(self._target_dir),
            "installed": [],
        }

        for section in installed_sections:
            src_section: Path = self._source_dir / section
            dst_section: Path = self._target_dir / section

            if not dst_section.exists():
                if src_section.is_dir():
                    shutil.copytree(src_section, dst_section)
                else:
                    dst_section.mkdir(parents=True, exist_ok=True)
                result_paths["installed"].append(section)
            elif force:
                if src_section.is_dir():
                    shutil.copytree(
                        src_section, dst_section, dirs_exist_ok=True
                    )
                result_paths["installed"].append(section)

        # Ensure default hosts.toml and config.toml exist if missing
        hosts_file: Path = self._target_dir / "hosts.toml"
        if not hosts_file.exists():
            hosts_file.write_text("[hosts]\n", encoding="utf-8")

        config_file: Path = self._target_dir / "config.toml"
        if not config_file.exists():
            config_file.write_text(
                "[project]\nname = \"global\"\ntheme = \"high_contrast\"\n",
                encoding="utf-8",
            )

        return result_paths


__all__: list[str] = [
    "NeuriInstaller",
]
