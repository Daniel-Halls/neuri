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


__all__: list[str] = [
    "PathResolver",
]
