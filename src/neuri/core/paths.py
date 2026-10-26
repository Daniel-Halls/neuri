"""Filesystem path resolution utilities for Neuri configuration and skills.

Provides centralized resolution of repository roots, package assets,
Tier-0 catalog indexes, and Tier-1 skill directories.
"""

from pathlib import Path


class PathResolver:
    """Resolves filesystem locations for repository assets and skill packs.

    Parameters
    ------------
    None

    Returns
    --------
        PathResolver: PathResolver instance
            Constructed path resolver utility.
    """

    @classmethod
    def get_repo_root(cls) -> Path:
        """Locate the root directory containing pyproject.toml or src/neuri.

        Parameters
        ------------
        None

        Returns
        --------
            Path: Path object
                Absolute filesystem path to the Neuri repository root.
        """
        current_file: Path = Path(__file__).resolve()
        # Traverse upwards from src/neuri/core/paths.py to find root
        for parent in current_file.parents:
            if (parent / "pyproject.toml").is_file():
                return parent
            if (parent / "skills" / "index.yaml").is_file():
                return parent

        # Fallback to 3 parents up (src/neuri/core -> repo root)
        fallback: Path = current_file.parents[3]
        return fallback

    @classmethod
    def get_base_template_dir(cls) -> Path:
        """Resolve path to the base 'neuri' distribution directory.

        Parameters
        ------------
        None

        Returns
        --------
            Path: Path object
                Filesystem path to the base neuri template directory.
        """
        repo_root: Path = cls.get_repo_root()
        base_dir: Path = repo_root / "neuri"
        return base_dir

    @classmethod
    def get_default_skills_index(cls) -> Path:
        """Resolve the path to the Tier-0 skills/index.yaml catalog.

        Parameters
        ------------
        None

        Returns
        --------
            Path: Path object
                Filesystem path to Tier-0 skills/index.yaml file.
        """
        installed: Path = Path.home() / ".neuri" / "skills" / "index.yaml"
        if installed.is_file():
            return installed

        base_index: Path = cls.get_base_template_dir() / "skills" / "index.yaml"
        if base_index.is_file():
            return base_index

        repo_root: Path = cls.get_repo_root()
        catalog_path: Path = repo_root / "skills" / "index.yaml"
        return catalog_path

    @classmethod
    def get_default_skills_dir(cls) -> Path:
        """Resolve the path to the root skills directory.

        Parameters
        ------------
        None

        Returns
        --------
            Path: Path object
                Filesystem path to skills directory.
        """
        installed: Path = Path.home() / ".neuri" / "skills"
        if installed.is_dir():
            return installed

        base_dir: Path = cls.get_base_template_dir() / "skills"
        if base_dir.is_dir():
            return base_dir

        repo_root: Path = cls.get_repo_root()
        skills_dir: Path = repo_root / "skills"
        return skills_dir

    @classmethod
    def resolve_skill_dir(
        cls, skill_id: str, workspace_dir: Path | None = None
    ) -> Path | None:
        """Resolve directory path for a skill ID from workspace or package.

        Parameters
        ------------
        skill_id: str
            Skill identifier or directory name.
        workspace_dir: Path | None
            Optional workspace directory to check for project-local overrides.
            Defaults to None.

        Returns
        --------
            Path | None: Path object or None
                Resolved skill directory path if exists, None otherwise.
        """
        candidates: list[str] = [
            skill_id,
            skill_id.replace("_", "-"),
            skill_id.replace("-", "_"),
        ]

        # 1. Check workspace project-local .neuri/skills/
        if workspace_dir is not None:
            local_skills_dir: Path = workspace_dir / ".neuri" / "skills"
            for candidate in candidates:
                local_target: Path = local_skills_dir / candidate
                if local_target.is_dir():
                    return local_target

        # 2. Check repository/package skills/ directory
        skills_root: Path = cls.get_default_skills_dir()
        for candidate in candidates:
            repo_target: Path = skills_root / candidate
            if repo_target.is_dir():
                return repo_target

        return None

    @classmethod
    def get_default_rules_dir(cls) -> Path:
        """Resolve the path to the root rules directory.

        Parameters
        ------------
        None

        Returns
        --------
            Path: Path object
                Filesystem path to the root rules directory.
        """
        installed: Path = Path.home() / ".neuri" / "rules"
        if installed.is_dir():
            return installed

        base_rules: Path = cls.get_base_template_dir() / "rules"
        if base_rules.is_dir():
            return base_rules

        repo_root: Path = cls.get_repo_root()
        rules_dir: Path = repo_root / "rules"
        return rules_dir

    @classmethod
    def resolve_rules_dirs(
        cls, workspace_dir: Path | None = None
    ) -> list[Path]:
        """Resolve existing rule directories across workspace, user, and repo.

        Parameters
        ------------
        workspace_dir: Path | None
            Optional workspace directory. Defaults to None.

        Returns
        --------
            list[Path]: list object
                Existing directory paths containing operational rules.
        """
        discovered: list[Path] = []
        if workspace_dir is not None:
            local_rules: Path = workspace_dir / ".neuri" / "rules"
            if local_rules.is_dir():
                discovered.append(local_rules)

        home_rules: Path = Path.home() / ".neuri" / "rules"
        if home_rules.is_dir():
            discovered.append(home_rules)

        base_rules: Path = cls.get_base_template_dir() / "rules"
        if base_rules.is_dir():
            discovered.append(base_rules)

        repo_rules: Path = cls.get_default_rules_dir()
        if repo_rules.is_dir() and repo_rules not in discovered:
            discovered.append(repo_rules)

        return discovered

    @classmethod
    def get_default_mcp_config(
        cls, workspace_dir: Path | None = None
    ) -> Path | None:
        """Resolve path to the MCP servers configuration file.

        Parameters
        ------------
        workspace_dir: Path | None
            Optional workspace directory. Defaults to None.

        Returns
        --------
            Path | None: Path object or None
                Resolved path to mcp_servers.json if found, else None.
        """
        if workspace_dir is not None:
            local_mcp: Path = workspace_dir / ".neuri" / "mcp" / "mcp_servers.json"
            if local_mcp.is_file():
                return local_mcp

        home_mcp: Path = Path.home() / ".neuri" / "mcp" / "mcp_servers.json"
        if home_mcp.is_file():
            return home_mcp

        base_mcp: Path = (
            cls.get_base_template_dir() / "mcp" / "mcp_servers.json"
        )
        if base_mcp.is_file():
            return base_mcp

        return None


__all__: list[str] = [
    "PathResolver",
]
