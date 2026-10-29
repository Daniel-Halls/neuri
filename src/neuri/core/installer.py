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

    def _index_installed_brain(self, brain_dir: Path) -> int:
        """Index markdown notes in the installed brain vault into SQLite FTS5.

        Parameters
        ------------
        brain_dir: Path
            Filesystem directory of the installed brain vault.

        Returns
        --------
            int: integer object
                Total number of indexed or updated notes.
        """
        try:
            from neuri.brain.indexer import BrainIndexer
            from neuri.brain.schemas import BrainScope

            db_path: Path = brain_dir / ".neuri-brain.db"
            indexer: BrainIndexer = BrainIndexer(db_path=db_path)
            metrics = indexer.sync_vault(
                vault_dir=brain_dir, scope=BrainScope.GLOBAL
            )
            return metrics.get("added", 0) + metrics.get("updated", 0)
        except Exception:
            return 0

    def install(self, force: bool = False) -> dict[str, Any]:
        """Install base global, skills, mcp, rules, and brain folders into target.

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
            "brain",
        ]

        if self._source_dir.is_dir():
            for item in sorted(self._source_dir.iterdir()):
                if item.name.startswith(".") or item.name == "__pycache__":
                    continue
                if item.name not in installed_sections:
                    installed_sections.append(item.name)

        result_paths: dict[str, Any] = {
            "target_dir": str(self._target_dir),
            "installed": [],
        }

        for section in installed_sections:
            src_section: Path = self._source_dir / section
            if not src_section.exists() and section == "brain":
                fallback_brain = PathResolver.get_repo_root() / "brain"
                if fallback_brain.is_dir():
                    src_section = fallback_brain

            dst_section: Path = self._target_dir / section

            if not dst_section.exists():
                if src_section.is_dir():
                    shutil.copytree(src_section, dst_section)
                elif src_section.is_file():
                    shutil.copy2(src_section, dst_section)
                else:
                    dst_section.mkdir(parents=True, exist_ok=True)
                result_paths["installed"].append(section)
            elif src_section.is_dir() and dst_section.is_dir():
                copied_any = False
                for sub in src_section.iterdir():
                    if sub.name.startswith(".") or sub.name == "__pycache__":
                        continue
                    dst_sub = dst_section / sub.name
                    if not dst_sub.exists():
                        if sub.is_dir():
                            shutil.copytree(sub, dst_sub)
                        elif sub.is_file():
                            shutil.copy2(sub, dst_sub)
                        copied_any = True
                    elif force:
                        if sub.is_dir():
                            shutil.copytree(sub, dst_sub, dirs_exist_ok=True)
                        elif sub.is_file():
                            shutil.copy2(sub, dst_sub)
                        copied_any = True
                if copied_any or force:
                    result_paths["installed"].append(section)
            elif force:
                if src_section.is_file():
                    shutil.copy2(src_section, dst_section)
                result_paths["installed"].append(section)

        # Index installed brain notes into SQLite FTS5
        brain_dir: Path = self._target_dir / "brain"
        if brain_dir.is_dir():
            self._index_installed_brain(brain_dir)

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

    def is_installed(self) -> bool:
        """Check whether base Neuri environment is properly installed in target.

        Verifies that target directory exists and contains all required
        subdirectories and foundational configuration files.

        Parameters
        ------------
        None

        Returns
        --------
            bool: boolean object
                True if all required sections exist in target directory,
                False otherwise.
        """
        required_sections: list[str] = [
            "global",
            "skills",
            "mcp",
            "rules",
            "themes",
            "brain",
        ]
        if not self._target_dir.is_dir():
            return False

        for section in required_sections:
            target_sub: Path = self._target_dir / section
            if not target_sub.exists():
                return False

        config_file: Path = self._target_dir / "config.toml"
        if not config_file.is_file():
            return False

        return True

    def ensure_installed(self, force: bool = False) -> bool:
        """Ensure base Neuri assets are present in target, installing if missing.

        Parameters
        ------------
        force: bool
            Whether to force overwrite existing assets. Defaults to False.

        Returns
        --------
            bool: boolean object
                True if an installation or update was executed, False if
                already installed and force was False.
        """
        if not force and self.is_installed():
            return False

        self.install(force=force)
        return True


__all__: list[str] = [
    "NeuriInstaller",
]
