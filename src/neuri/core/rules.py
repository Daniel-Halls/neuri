"""Dynamic operational rules loader for Neuri agents.

Discovers and compiles markdown rule documents (.md, .txt) from workspace
.neuri/rules/, global ~/.neuri/rules/, and repository rules/ directories.
"""

from pathlib import Path

from neuri.core.paths import PathResolver


class RuleLoader:
    """Manages loading of dynamic operational rules for Neuri agents.

    Parameters
    ------------
    workspace_dir: Path | None
        Optional project workspace directory. Defaults to None.
    rules_dir: Path | None
        Optional explicit rules directory path. Defaults to None.

    Returns
    --------
        RuleLoader: RuleLoader instance
            Constructed rule loader.
    """

    def __init__(
        self,
        workspace_dir: Path | None = None,
        rules_dir: Path | None = None,
    ) -> None:
        """Initialize RuleLoader with optional workspace or explicit directory.

        Parameters
        ------------
        workspace_dir: Path | None
            Project workspace root directory. Defaults to None.
        rules_dir: Path | None
            Explicit directory containing rule files. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes loader paths.
        """
        self._workspace_dir: Path | None = workspace_dir
        self._rules_dir: Path | None = rules_dir

    def get_rule_directories(self) -> list[Path]:
        """Collect all active rule directories in lookup precedence order.

        Parameters
        ------------
        None

        Returns
        --------
            list[Path]: list object
                Existing directory paths searched for rule files.
        """
        search_dirs: list[Path] = []
        if self._rules_dir is not None and self._rules_dir.is_dir():
            search_dirs.append(self._rules_dir)

        discovered: list[Path] = PathResolver.resolve_rules_dirs(
            self._workspace_dir
        )
        for directory in discovered:
            if directory not in search_dirs:
                search_dirs.append(directory)

        return search_dirs

    def load_rules(self, role: str | None = None) -> str:
        """Load and concatenate rule contents relevant to a role or general use.

        Parameters
        ------------
        role: str | None
            Optional agent role name (e.g. 'pipeline_engineer'). Defaults to None.

        Returns
        --------
            str: string object
                Combined rule text from discovered files, or empty string.
        """
        collected_blocks: list[str] = []
        seen_filenames: set[str] = set()

        for directory in self.get_rule_directories():
            try:
                entries: list[Path] = sorted(directory.iterdir())
            except Exception:
                continue

            for rule_file in entries:
                if not rule_file.is_file():
                    continue
                if rule_file.suffix.lower() not in (".md", ".txt"):
                    continue
                if rule_file.name.startswith("."):
                    continue
                if rule_file.name in seen_filenames:
                    continue

                stem: str = rule_file.stem.lower()
                is_general: bool = (
                    stem in ("general", "rules", "default", "global", "common")
                    or stem.startswith("global_")
                    or stem.startswith("global-")
                )
                is_matching_role: bool = False
                if role:
                    role_clean: str = role.lower()
                    role_dash: str = role.replace("_", "-").lower()
                    is_matching_role = (
                        stem == role_clean
                        or stem == role_dash
                        or stem.startswith(f"{role_clean}_")
                        or stem.startswith(f"{role_dash}-")
                    )

                if role is not None and not (is_general or is_matching_role):
                    continue

                try:
                    content: str = rule_file.read_text(
                        encoding="utf-8"
                    ).strip()
                    if content:
                        collected_blocks.append(content)
                        seen_filenames.add(rule_file.name)
                except Exception:
                    pass

        joined_rules: str = "\n\n".join(collected_blocks)
        return joined_rules

    @classmethod
    def load_master_prompt(
        cls, workspace_dir: Path | None = None
    ) -> str:
        """Load the master grounding prompt for all sessions.

        Searches for master_prompt.md or prompt.md in:
        1. <workspace>/.neuri/master_prompt.md
        2. ~/.neuri/master_prompt.md
        3. <repo_root>/master_prompt.md
        4. <repo_root>/rules/master_prompt.md

        Parameters
        ------------
        workspace_dir: Path | None
            Optional workspace directory. Defaults to None.

        Returns
        --------
            str: string object
                Master grounding prompt text, or empty string if not found.
        """
        candidates: list[Path] = []
        if workspace_dir is not None:
            candidates.append(
                workspace_dir / ".neuri" / "global" / "master_prompt.md"
            )
            candidates.append(workspace_dir / ".neuri" / "master_prompt.md")
            candidates.append(workspace_dir / ".neuri" / "prompt.md")

        home_dir: Path = Path.home() / ".neuri"
        candidates.append(home_dir / "global" / "master_prompt.md")
        candidates.append(home_dir / "master_prompt.md")
        candidates.append(home_dir / "prompt.md")

        base_template: Path = PathResolver.get_base_template_dir()
        candidates.append(base_template / "global" / "master_prompt.md")

        repo_root: Path = PathResolver.get_repo_root()
        candidates.append(repo_root / "master_prompt.md")
        candidates.append(repo_root / "rules" / "master_prompt.md")

        for cand in candidates:
            if cand.is_file():
                try:
                    txt: str = cand.read_text(encoding="utf-8").strip()
                    if txt:
                        return txt
                except Exception:
                    pass

        return ""

    @classmethod
    def load_agent_rules(
        cls,
        role: str | None = None,
        workspace_dir: Path | None = None,
    ) -> str:
        """Load dynamic rules for an agent role across all rule directories.

        Parameters
        ------------
        role: str | None
            Agent role name or None for general rules. Defaults to None.
        workspace_dir: Path | None
            Optional workspace directory. Defaults to None.

        Returns
        --------
            str: string object
                Combined operational rules string, or empty string if none.
        """
        loader: RuleLoader = cls(workspace_dir=workspace_dir)
        rules_text: str = loader.load_rules(role=role)
        return rules_text


__all__: list[str] = [
    "RuleLoader",
]
