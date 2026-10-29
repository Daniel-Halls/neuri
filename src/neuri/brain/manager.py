"""Neuri Brain High-Level Manager and Coordinator.

Orchestrates Global and Project Obsidian vaults, incremental indexing,
tiered semantic retrieval, note creation, observation recording, and Obsidian
deep-linking integration.
"""

from pathlib import Path
import shutil
import urllib.parse

from neuri.brain.indexer import BrainIndexer
from neuri.brain.parser import BrainParser
from neuri.brain.retriever import BrainRetriever
from neuri.brain.schemas import (
    BrainContextCapsule,
    BrainEntity,
    BrainNote,
    BrainObservation,
    BrainRelation,
    BrainScope,
    BrainSearchResult,
    BrainStats,
    ObservationCategory,
    RelationType,
)


class BrainManager:
    """Central facade managing Obsidian vaults, indexing, and memory retrieval.

    Parameters
    ------------
    global_vault_dir: Path
        Filesystem directory for the Global Obsidian vault.
    project_vault_dir: Path
        Filesystem directory for the Project Obsidian vault.
    db_path: Path | None
        Optional explicit path to SQLite index database. Defaults to None.

    Returns
    --------
        BrainManager: BrainManager instance
            Constructed brain manager coordinator.
    """

    def __init__(
        self,
        global_vault_dir: Path,
        project_vault_dir: Path,
        db_path: Path | None = None,
    ) -> None:
        """Initialize BrainManager with vault locations and SQLite index.

        Parameters
        ------------
        global_vault_dir: Path
            Filesystem directory for the Global Obsidian vault.
        project_vault_dir: Path
            Filesystem directory for the Project Obsidian vault.
        db_path: Path | None
            Optional path to SQLite index database. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes manager state.
        """
        self._global_vault: Path = global_vault_dir.resolve()
        self._project_vault: Path = project_vault_dir.resolve()

        resolved_db: Path = (
            db_path.resolve()
            if db_path is not None
            else self._global_vault / ".neuri-brain.db"
        )
        self._indexer: BrainIndexer = BrainIndexer(db_path=resolved_db)
        self._retriever: BrainRetriever = BrainRetriever(indexer=self._indexer)
        self._parser: BrainParser = BrainParser()

    @property
    def global_vault(self) -> Path:
        """Get the resolved global vault directory path.

        Parameters
        ------------
        None

        Returns
        --------
            Path: Path object
                Filesystem directory of the global vault.
        """
        return self._global_vault

    @property
    def project_vault(self) -> Path:
        """Get the resolved project vault directory path.

        Parameters
        ------------
        None

        Returns
        --------
            Path: Path object
                Filesystem directory of the project vault.
        """
        return self._project_vault

    def init_global_vault(self) -> list[Path]:
        """Scaffold global vault directory hierarchy and starter index notes.

        Parameters
        ------------
        None

        Returns
        --------
            list[Path]: list object
                List of created or verified starter note paths.
        """
        self._global_vault.mkdir(parents=True, exist_ok=True)
        folders: list[str] = [
            "00_Index",
            "01_Literature",
            "02_Methods",
            "03_Concepts",
            "04_Templates",
        ]
        for folder in folders:
            (self._global_vault / folder).mkdir(parents=True, exist_ok=True)

        created_files: list[Path] = []

        priorities_file: Path = (
            self._global_vault / "00_Index" / "Research Priorities.md"
        )
        if not priorities_file.is_file():
            obs = [
                BrainObservation(
                    category=ObservationCategory.HYPOTHESIS,
                    content=(
                        "Track methodological benchmarks for fMRI "
                        "and M/EEG pipelines"
                    ),
                    tags=["priorities", "methods"],
                ),
                BrainObservation(
                    category=ObservationCategory.DECISION,
                    content=(
                        "Enforce strict PHI sanitization before "
                        "external LLM queries"
                    ),
                    tags=["security", "phi"],
                ),
            ]
            md: str = self._parser.render_markdown_note(
                title="Research Priorities",
                observations=obs,
                relations=[],
                body_prose=(
                    "Core lab-wide scientific questions and active "
                    "research objectives."
                ),
                frontmatter_extra={"type": "priority", "scope": "global"},
            )
            priorities_file.write_text(md, encoding="utf-8")
            created_files.append(priorities_file)

        standards_file: Path = (
            self._global_vault / "00_Index" / "Lab Standards.md"
        )
        if not standards_file.is_file():
            obs = [
                BrainObservation(
                    category=ObservationCategory.PARAMETER,
                    content=(
                        "Default spatial smoothing FWHM set to 6.0 mm "
                        "for cortical BOLD"
                    ),
                    tags=["fwhm", "smoothing"],
                ),
                BrainObservation(
                    category=ObservationCategory.LIMITATION,
                    content=(
                        "Framewise displacement > 0.5 mm flagged as motion anomaly"
                    ),
                    tags=["motion", "qa"],
                ),
            ]
            md = self._parser.render_markdown_note(
                title="Lab Standards",
                observations=obs,
                relations=[
                    BrainRelation(
                        relation_type=RelationType.EXTENDS,
                        target_permalink="00_Index/Research Priorities",
                        target_title="Research Priorities",
                    )
                ],
                body_prose="Consensus preprocessing parameters and quality thresholds.",
                frontmatter_extra={"type": "standard", "scope": "global"},
            )
            standards_file.write_text(md, encoding="utf-8")
            created_files.append(standards_file)

        # Synchronize pipeline documentation if available
        target_doc: Path = self._global_vault / "doc"
        if not target_doc.is_dir() or not any(target_doc.iterdir()):
            from neuri.core.paths import PathResolver

            src_doc: Path = (
                PathResolver.get_base_template_dir() / "brain" / "doc"
            )
            if not src_doc.is_dir():
                src_doc = PathResolver.get_repo_root() / "brain" / "doc"
            if src_doc.is_dir():
                shutil.copytree(src_doc, target_doc, dirs_exist_ok=True)

        self.sync_all()
        return created_files

    def init_project_vault(self) -> list[Path]:
        """Scaffold project vault directory hierarchy and study overview.

        Parameters
        ------------
        None

        Returns
        --------
            list[Path]: list object
                List of created or verified project note paths.
        """
        self._project_vault.mkdir(parents=True, exist_ok=True)
        folders: list[str] = [
            "Decisions",
            "Workflows",
            "QA_Log",
            "References",
        ]
        for folder in folders:
            (self._project_vault / folder).mkdir(parents=True, exist_ok=True)

        created_files: list[Path] = []
        overview_file: Path = self._project_vault / "Study_Overview.md"
        if not overview_file.is_file():
            obs = [
                BrainObservation(
                    category=ObservationCategory.DECISION,
                    content="Dataset structured following BIDS v1.9 specification",
                    tags=["bids", "dataset"],
                )
            ]
            md: str = self._parser.render_markdown_note(
                title="Study Overview",
                observations=obs,
                relations=[
                    BrainRelation(
                        relation_type=RelationType.APPLIES_TO,
                        target_permalink="00_Index/Lab Standards",
                        target_title="Lab Standards",
                    )
                ],
                body_prose=(
                    "Operational notebook for study hypotheses, cohort runs, "
                    "and QA logs."
                ),
                frontmatter_extra={"type": "study", "scope": "project"},
            )
            overview_file.write_text(md, encoding="utf-8")
            created_files.append(overview_file)

        self.sync_all()
        return created_files

    def sync_all(self) -> dict[str, dict[str, int]]:
        """Synchronize both Global and Project vaults with SQLite index.

        Parameters
        ------------
        None

        Returns
        --------
            dict[str, dict[str, int]]: dictionary object
                Metrics for global and project vault incremental syncs.
        """
        global_metrics: dict[str, int] = self._indexer.sync_vault(
            vault_dir=self._global_vault,
            scope=BrainScope.GLOBAL,
        )
        project_metrics: dict[str, int] = self._indexer.sync_vault(
            vault_dir=self._project_vault,
            scope=BrainScope.PROJECT,
        )
        combined: dict[str, dict[str, int]] = {
            "global": global_metrics,
            "project": project_metrics,
        }
        return combined

    def search(
        self,
        query: str,
        limit: int = 8,
        scope: BrainScope | None = None,
        category: ObservationCategory | None = None,
    ) -> list[BrainSearchResult]:
        """Search notes and observations across indexed vaults.

        Parameters
        ------------
        query: str
            Text search query.
        limit: int
            Maximum results. Defaults to 8.
        scope: BrainScope | None
            Optional scope filter. Defaults to None.
        category: ObservationCategory | None
            Optional category filter. Defaults to None.

        Returns
        --------
            list[BrainSearchResult]: list object
                Ranked search results.
        """
        results: list[BrainSearchResult] = self._retriever.search_notes(
            query=query, limit=limit, scope=scope, category=category
        )
        return results

    def build_context(
        self,
        query: str,
        max_tokens: int = 450,
        depth: int = 1,
    ) -> BrainContextCapsule:
        """Construct low-context Tier-0 progressive disclosure capsule.

        Parameters
        ------------
        query: str
            Topic or task query.
        max_tokens: int
            Strict upper token limit. Defaults to 450.
        depth: int
            Hop depth for relations. Defaults to 1.

        Returns
        --------
            BrainContextCapsule: BrainContextCapsule object
                Token-budgeted Markdown memory capsule.
        """
        capsule: BrainContextCapsule = self._retriever.build_context(
            query=query, max_tokens=max_tokens, depth=depth
        )
        return capsule

    def write_note(
        self,
        title: str,
        folder: str,
        observations: list[BrainObservation],
        relations: list[BrainRelation],
        body_prose: str = "",
        scope: BrainScope = BrainScope.PROJECT,
        tags: list[str] | None = None,
    ) -> Path:
        """Create and index a new structured Markdown note in the vault.

        Parameters
        ------------
        title: str
            Note title.
        folder: str
            Relative subfolder within the vault (e.g. 'Decisions').
        observations: list[BrainObservation]
            Atomic observations list.
        relations: list[BrainRelation]
            Semantic relations list.
        body_prose: str
            Freeform prose text. Defaults to ''.
        scope: BrainScope
            Target vault scope. Defaults to BrainScope.PROJECT.
        tags: list[str] | None
            Optional tags list. Defaults to None.

        Returns
        --------
            Path: Path object
                Filesystem path to the written Markdown file.
        """
        vault_root: Path = (
            self._project_vault
            if scope == BrainScope.PROJECT
            else self._global_vault
        )
        dest_dir: Path = vault_root / folder
        dest_dir.mkdir(parents=True, exist_ok=True)

        filename: str = f"{title.replace(' ', '_')}.md"
        file_path: Path = dest_dir / filename

        fm_extra: dict[str, Any] = {
            "scope": scope.value,
        }
        if tags:
            fm_extra["tags"] = tags

        md_content: str = self._parser.render_markdown_note(
            title=title,
            observations=observations,
            relations=relations,
            body_prose=body_prose,
            frontmatter_extra=fm_extra,
        )
        file_path.write_text(md_content, encoding="utf-8")

        rel_path: str = str(file_path.relative_to(vault_root))
        stat = file_path.stat()
        parsed: BrainNote = self._parser.parse_markdown_content(
            raw_text=md_content,
            relative_path=rel_path,
            scope=scope,
            mtime_ns=stat.st_mtime_ns,
        )
        self._indexer.upsert_note(note=parsed)
        return file_path

    def remember_observation(
        self,
        observation: BrainObservation,
        permalink: str = "00_Index/Quick_Notes",
        scope: BrainScope = BrainScope.PROJECT,
    ) -> bool:
        """Append an atomic observation to an existing or quick note.

        Parameters
        ------------
        observation: BrainObservation
            Atomic observation to record.
        permalink: str
            Target note permalink. Defaults to '00_Index/Quick_Notes'.
        scope: BrainScope
            Target vault scope. Defaults to BrainScope.PROJECT.

        Returns
        --------
            bool: boolean object
                True if observation successfully appended and indexed.
        """
        vault_root: Path = (
            self._project_vault
            if scope == BrainScope.PROJECT
            else self._global_vault
        )
        file_path: Path = vault_root / f"{permalink}.md"

        if not file_path.is_file():
            self.write_note(
                title=Path(permalink).stem.replace("_", " "),
                folder=str(Path(permalink).parent),
                observations=[observation],
                relations=[],
                body_prose="Auto-generated notes ledger.",
                scope=scope,
            )
            return True

        raw_text: str = file_path.read_text(encoding="utf-8")
        tags_str: str = (
            " " + " ".join(f"#{t}" for t in observation.tags)
            if observation.tags
            else ""
        )
        bullet: str = (
            f"- [{observation.category.value}] {observation.content}{tags_str}\n"
        )

        if "### Observations" in raw_text:
            updated_text: str = raw_text.replace(
                "### Observations\n",
                f"### Observations\n{bullet}",
                1,
            )
        else:
            updated_text = f"{raw_text.strip()}\n\n### Observations\n{bullet}\n"

        file_path.write_text(updated_text, encoding="utf-8")
        rel_path: str = str(file_path.relative_to(vault_root))
        stat = file_path.stat()
        parsed: BrainNote = self._parser.parse_markdown_content(
            raw_text=updated_text,
            relative_path=rel_path,
            scope=scope,
            mtime_ns=stat.st_mtime_ns,
        )
        self._indexer.upsert_note(note=parsed)
        return True

    def get_stats(self) -> BrainStats:
        """Retrieve aggregated statistics across all managed vaults.

        Parameters
        ------------
        None

        Returns
        --------
            BrainStats: BrainStats object
                Populated statistics model.
        """
        counts: dict[str, int] = self._indexer.get_counts()
        unresolved: list[str] = self._indexer.get_unresolved_links()

        stats: BrainStats = BrainStats(
            global_vault_path=str(self._global_vault),
            project_vault_path=str(self._project_vault),
            global_notes_count=counts.get("global_notes", 0),
            project_notes_count=counts.get("project_notes", 0),
            total_observations_count=counts.get("total_observations", 0),
            total_relations_count=counts.get("total_relations", 0),
            unresolved_links=unresolved,
        )
        return stats

    def get_obsidian_uri(self, file_path: Path) -> str:
        """Construct obsidian://open deep link URI for a given note file.

        Parameters
        ------------
        file_path: Path
            Filesystem path to the Markdown file.

        Returns
        --------
            str: string object
                URI string suitable for launching in Obsidian app.
        """
        resolved: Path = file_path.resolve()
        quoted_path: str = urllib.parse.quote(str(resolved))
        uri: str = f"obsidian://open?path={quoted_path}"
        return uri


__all__: list[str] = [
    "BrainManager",
]
