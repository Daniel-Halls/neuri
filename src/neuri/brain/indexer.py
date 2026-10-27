"""Neuri Brain Incremental Semantic Indexer.

Manages SQLite WAL database with FTS5 full-text indexing, storing entities,
atomic observations, directed relationships, and providing fast incremental
sync with filesystem mtime and SHA-256 change detection.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Generator

from neuri.brain.parser import BrainParser
from neuri.brain.schemas import (
    BrainEntity,
    BrainNote,
    BrainObservation,
    BrainRelation,
    BrainScope,
    ObservationCategory,
    RelationType,
)


class BrainIndexer:
    """Incremental SQLite indexer for Brain notes and semantic graph.

    Parameters
    ------------
    db_path: Path
        Filesystem path to the SQLite database file.

    Returns
    --------
        BrainIndexer: BrainIndexer instance
            Constructed indexer instance.
    """

    def __init__(self, db_path: Path) -> None:
        """Initialize indexer and ensure schema migrations are applied.

        Parameters
        ------------
        db_path: Path
            Filesystem path to the SQLite database file.

        Returns
        --------
            None: NoneType object
                Initializes indexer state and schema.
        """
        self._db_path: Path = db_path.resolve()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._parser: BrainParser = BrainParser()
        self._initialize_schema()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Provide a context-managed SQLite connection with foreign keys.

        Parameters
        ------------
        None

        Returns
        --------
            Generator[sqlite3.Connection, None, None]: generator object
                Yields active SQLite connection within transaction context.
        """
        conn: sqlite3.Connection = sqlite3.connect(
            str(self._db_path),
            timeout=30.0,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialize_schema(self) -> None:
        """Create database tables, indexes, and FTS5 virtual tables.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Initializes database schema.
        """
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS brain_entities (
                    entity_id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    title TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    mtime_ns INTEGER NOT NULL,
                    frontmatter_json TEXT NOT NULL,
                    summary_excerpt TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_entities_scope
                    ON brain_entities(scope);
                CREATE INDEX IF NOT EXISTS idx_entities_filepath
                    ON brain_entities(file_path);

                CREATE TABLE IF NOT EXISTS brain_observations (
                    observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    line_number INTEGER,
                    FOREIGN KEY (entity_id) REFERENCES brain_entities(entity_id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_obs_entity
                    ON brain_observations(entity_id);
                CREATE INDEX IF NOT EXISTS idx_obs_category
                    ON brain_observations(category);

                CREATE TABLE IF NOT EXISTS brain_relations (
                    relation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_entity_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    target_permalink TEXT NOT NULL,
                    target_title TEXT,
                    context_snippet TEXT,
                    FOREIGN KEY (source_entity_id)
                        REFERENCES brain_entities(entity_id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_rel_source
                    ON brain_relations(source_entity_id);
                CREATE INDEX IF NOT EXISTS idx_rel_target
                    ON brain_relations(target_permalink);
                CREATE INDEX IF NOT EXISTS idx_rel_type
                    ON brain_relations(relation_type);

                CREATE VIRTUAL TABLE IF NOT EXISTS brain_fts USING fts5(
                    entity_id UNINDEXED,
                    title,
                    tags,
                    observations,
                    summary,
                    tokenize='porter unicode61'
                );
                """
            )

    def sync_vault(
        self, vault_dir: Path, scope: BrainScope
    ) -> dict[str, int]:
        """Synchronize Markdown vault files with the SQLite index.

        Parameters
        ------------
        vault_dir: Path
            Directory path to the Obsidian vault root.
        scope: BrainScope
            Scope classification (global or project).

        Returns
        --------
            dict[str, int]: dictionary object
                Metrics with added, updated, deleted, and unchanged note counts.
        """
        metrics: dict[str, int] = {
            "added": 0,
            "updated": 0,
            "deleted": 0,
            "unchanged": 0,
        }
        if not vault_dir.is_dir():
            return metrics

        existing_records: dict[str, tuple[str, int, str]] = (
            self._load_existing_records(scope=scope)
        )
        seen_paths: set[str] = set()

        for file_path in vault_dir.rglob("*.md"):
            rel_path: str = str(file_path.relative_to(vault_dir))
            # Ignore hidden folders like .obsidian, .git, .trash
            parts: tuple[str, ...] = file_path.relative_to(vault_dir).parts
            if any(part.startswith(".") for part in parts):
                continue

            seen_paths.add(rel_path)
            stat = file_path.stat()
            current_mtime: int = stat.st_mtime_ns

            if rel_path in existing_records:
                entity_id, prev_mtime, prev_hash = existing_records[rel_path]
                if current_mtime == prev_mtime:
                    metrics["unchanged"] += 1
                    continue

                raw_text: str = file_path.read_text(encoding="utf-8")
                parsed_note: BrainNote = self._parser.parse_markdown_content(
                    raw_text=raw_text,
                    relative_path=rel_path,
                    scope=scope,
                    mtime_ns=current_mtime,
                )
                if parsed_note.entity.content_sha256 == prev_hash:
                    self._update_mtime(
                        entity_id=entity_id, mtime_ns=current_mtime
                    )
                    metrics["unchanged"] += 1
                    continue

                self.upsert_note(note=parsed_note)
                metrics["updated"] += 1
            else:
                raw_text = file_path.read_text(encoding="utf-8")
                parsed_note = self._parser.parse_markdown_content(
                    raw_text=raw_text,
                    relative_path=rel_path,
                    scope=scope,
                    mtime_ns=current_mtime,
                )
                self.upsert_note(note=parsed_note)
                metrics["added"] += 1

        # Prune deleted files
        for rel_path, (entity_id, _, _) in existing_records.items():
            if rel_path not in seen_paths:
                self.delete_entity(entity_id=entity_id)
                metrics["deleted"] += 1

        return metrics

    def upsert_note(self, note: BrainNote) -> None:
        """Insert or replace a note and its observations, relations, and FTS.

        Parameters
        ------------
        note: BrainNote
            Parsed BrainNote instance to store.

        Returns
        --------
            None: NoneType object
                Persists note state into database.
        """
        now_iso: str = datetime.now(timezone.utc).isoformat()
        all_tags: list[str] = []
        for obs in note.observations:
            for tag in obs.tags:
                if tag not in all_tags:
                    all_tags.append(tag)

        obs_text: str = " ".join(o.content for o in note.observations)
        tags_str: str = " ".join(all_tags)

        with self._get_connection() as conn:
            # 1. Upsert entity
            conn.execute(
                """
                INSERT INTO brain_entities (
                    entity_id, scope, title, entity_type, file_path,
                    content_sha256, mtime_ns, frontmatter_json,
                    summary_excerpt, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(entity_id) DO UPDATE SET
                    scope=excluded.scope,
                    title=excluded.title,
                    entity_type=excluded.entity_type,
                    file_path=excluded.file_path,
                    content_sha256=excluded.content_sha256,
                    mtime_ns=excluded.mtime_ns,
                    frontmatter_json=excluded.frontmatter_json,
                    summary_excerpt=excluded.summary_excerpt,
                    updated_at=excluded.updated_at
                """,
                (
                    note.entity.entity_id,
                    note.entity.scope.value,
                    note.entity.title,
                    note.entity.entity_type,
                    note.entity.file_path,
                    note.entity.content_sha256,
                    note.entity.mtime_ns,
                    json.dumps(note.entity.frontmatter),
                    note.entity.summary_excerpt,
                    now_iso,
                    now_iso,
                ),
            )

            # 2. Refresh observations
            conn.execute(
                "DELETE FROM brain_observations WHERE entity_id = ?",
                (note.entity.entity_id,),
            )
            for obs in note.observations:
                conn.execute(
                    """
                    INSERT INTO brain_observations (
                        entity_id, category, content, tags_json, line_number
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        note.entity.entity_id,
                        obs.category.value,
                        obs.content,
                        json.dumps(obs.tags),
                        obs.line_number,
                    ),
                )

            # 3. Refresh relations
            conn.execute(
                "DELETE FROM brain_relations WHERE source_entity_id = ?",
                (note.entity.entity_id,),
            )
            for rel in note.relations:
                conn.execute(
                    """
                    INSERT INTO brain_relations (
                        source_entity_id, relation_type, target_permalink,
                        target_title, context_snippet
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        note.entity.entity_id,
                        rel.relation_type.value,
                        rel.target_permalink,
                        rel.target_title,
                        rel.context_snippet,
                    ),
                )

            # 4. Refresh FTS
            conn.execute(
                "DELETE FROM brain_fts WHERE entity_id = ?",
                (note.entity.entity_id,),
            )
            conn.execute(
                """
                INSERT INTO brain_fts (
                    entity_id, title, tags, observations, summary
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    note.entity.entity_id,
                    note.entity.title,
                    tags_str,
                    obs_text,
                    note.entity.summary_excerpt,
                ),
            )

    def delete_entity(self, entity_id: str) -> None:
        """Delete an entity and associated records from the index.

        Parameters
        ------------
        entity_id: str
            Unique permalink identifier to delete.

        Returns
        --------
            None: NoneType object
                Removes record and FTS entry.
        """
        with self._get_connection() as conn:
            conn.execute(
                "DELETE FROM brain_entities WHERE entity_id = ?",
                (entity_id,),
            )
            conn.execute(
                "DELETE FROM brain_fts WHERE entity_id = ?",
                (entity_id,),
            )

    def get_entity(self, entity_id: str) -> BrainEntity | None:
        """Retrieve indexed entity metadata by entity permalink identifier.

        Parameters
        ------------
        entity_id: str
            Unique permalink identifier.

        Returns
        --------
            BrainEntity | None: BrainEntity object or None
                Found entity model or None.
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT entity_id, scope, title, entity_type, file_path,
                       content_sha256, mtime_ns, frontmatter_json,
                       summary_excerpt
                FROM brain_entities
                WHERE entity_id = ?
                """,
                (entity_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            obs_count: int = conn.execute(
                "SELECT COUNT(*) FROM brain_observations WHERE entity_id = ?",
                (entity_id,),
            ).fetchone()[0]

            rel_count: int = conn.execute(
                "SELECT COUNT(*) FROM brain_relations WHERE source_entity_id = ?",
                (entity_id,),
            ).fetchone()[0]

            entity: BrainEntity = BrainEntity(
                entity_id=row["entity_id"],
                scope=BrainScope(row["scope"]),
                title=row["title"],
                entity_type=row["entity_type"],
                file_path=row["file_path"],
                content_sha256=row["content_sha256"],
                mtime_ns=row["mtime_ns"],
                frontmatter=json.loads(row["frontmatter_json"]),
                summary_excerpt=row["summary_excerpt"],
                observations_count=obs_count,
                relations_count=rel_count,
            )
            return entity

    def get_observations_for_entity(
        self, entity_id: str
    ) -> list[BrainObservation]:
        """Fetch all atomic observations for a given entity identifier.

        Parameters
        ------------
        entity_id: str
            Unique permalink identifier.

        Returns
        --------
            list[BrainObservation]: list object
                Extracted observations ordered by line number.
        """
        observations: list[BrainObservation] = []
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT category, content, tags_json, line_number
                FROM brain_observations
                WHERE entity_id = ?
                ORDER BY line_number ASC
                """,
                (entity_id,),
            )
            for row in cursor.fetchall():
                obs: BrainObservation = BrainObservation(
                    category=ObservationCategory(row["category"]),
                    content=row["content"],
                    tags=json.loads(row["tags_json"]),
                    line_number=row["line_number"],
                )
                observations.append(obs)
        return observations

    def get_relations_for_entity(
        self, entity_id: str
    ) -> list[BrainRelation]:
        """Fetch outgoing relations for a given source entity identifier.

        Parameters
        ------------
        entity_id: str
            Source entity permalink identifier.

        Returns
        --------
            list[BrainRelation]: list object
                Outgoing directed relations.
        """
        relations: list[BrainRelation] = []
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT relation_type, target_permalink, target_title,
                       context_snippet
                FROM brain_relations
                WHERE source_entity_id = ?
                """,
                (entity_id,),
            )
            for row in cursor.fetchall():
                rel: BrainRelation = BrainRelation(
                    relation_type=RelationType(row["relation_type"]),
                    target_permalink=row["target_permalink"],
                    target_title=row["target_title"],
                    context_snippet=row["context_snippet"],
                )
                relations.append(rel)
        return relations

    def get_backlinks_for_entity(
        self, target_permalink: str
    ) -> list[BrainRelation]:
        """Fetch incoming relations targeting a given permalink.

        Parameters
        ------------
        target_permalink: str
            Target entity permalink identifier.

        Returns
        --------
            list[BrainRelation]: list object
                Incoming relations referencing target.
        """
        relations: list[BrainRelation] = []
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT relation_type, source_entity_id, context_snippet
                FROM brain_relations
                WHERE lower(target_permalink) = lower(?)
                """,
                (target_permalink,),
            )
            for row in cursor.fetchall():
                rel: BrainRelation = BrainRelation(
                    relation_type=RelationType(row["relation_type"]),
                    target_permalink=row["source_entity_id"],
                    target_title=None,
                    context_snippet=row["context_snippet"],
                )
                relations.append(rel)
        return relations

    def get_unresolved_links(self) -> list[str]:
        """Identify forward WikiLinks whose target entity does not exist.

        Parameters
        ------------
        None

        Returns
        --------
            list[str]: list object
                Unique list of target permalinks not found in index.
        """
        unresolved: list[str] = []
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT DISTINCT r.target_permalink
                FROM brain_relations r
                LEFT JOIN brain_entities e
                    ON lower(r.target_permalink) = lower(e.entity_id)
                WHERE e.entity_id IS NULL
                ORDER BY r.target_permalink ASC
                """
            )
            for row in cursor.fetchall():
                unresolved.append(row[0])
        return unresolved

    def get_counts(self) -> dict[str, int]:
        """Return total counts of entities, observations, and relations.

        Parameters
        ------------
        None

        Returns
        --------
            dict[str, int]: dictionary object
                Count metrics for entities, observations, and relations.
        """
        with self._get_connection() as conn:
            global_count: int = conn.execute(
                "SELECT COUNT(*) FROM brain_entities WHERE scope = 'global'"
            ).fetchone()[0]
            project_count: int = conn.execute(
                "SELECT COUNT(*) FROM brain_entities WHERE scope = 'project'"
            ).fetchone()[0]
            obs_count: int = conn.execute(
                "SELECT COUNT(*) FROM brain_observations"
            ).fetchone()[0]
            rel_count: int = conn.execute(
                "SELECT COUNT(*) FROM brain_relations"
            ).fetchone()[0]

            counts: dict[str, int] = {
                "global_notes": global_count,
                "project_notes": project_count,
                "total_observations": obs_count,
                "total_relations": rel_count,
            }
            return counts

    def _load_existing_records(
        self, scope: BrainScope
    ) -> dict[str, tuple[str, int, str]]:
        """Load mapping of relative file paths to mtime and hash.

        Parameters
        ------------
        scope: BrainScope
            Scope classification.

        Returns
        --------
            dict[str, tuple[str, int, str]]: dictionary object
                Mapping from file_path to (entity_id, mtime_ns, content_sha256).
        """
        records: dict[str, tuple[str, int, str]] = {}
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT entity_id, file_path, mtime_ns, content_sha256
                FROM brain_entities
                WHERE scope = ?
                """,
                (scope.value,),
            )
            for row in cursor.fetchall():
                records[row["file_path"]] = (
                    row["entity_id"],
                    row["mtime_ns"],
                    row["content_sha256"],
                )
        return records

    def _update_mtime(self, entity_id: str, mtime_ns: int) -> None:
        """Update modification timestamp for an entity in database.

        Parameters
        ------------
        entity_id: str
            Unique permalink identifier.
        mtime_ns: int
            New filesystem timestamp in nanoseconds.

        Returns
        --------
            None: NoneType object
                Updates database record.
        """
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE brain_entities SET mtime_ns = ? WHERE entity_id = ?",
                (mtime_ns, entity_id),
            )


__all__: list[str] = [
    "BrainIndexer",
]
