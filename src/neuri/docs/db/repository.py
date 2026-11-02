"""Database repository for querying and persisting neuroimaging documentation.

Provides SQLite connection management, pipeline resolution, full-text FTS5
search, and fallback LIKE matching for documentation chunks.
"""

import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any, cast

from neuri.core.paths import PathResolver
from neuri.docs.db.schema import DocsDBSchema
from neuri.docs.models import (
    DocChunkRecord,
    DocSearchResult,
    DocType,
    PipelineMetadata,
)


class DocsRepository:
    """Repository handling persistence and retrieval of documentation chunks.

    Parameters
    ------------
    db_path: Path | None
        Optional explicit SQLite database filesystem path. Defaults to None.

    Returns
    --------
        DocsRepository: DocsRepository instance
            Constructed repository instance.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize DocsRepository with resolved database file path.

        Parameters
        ------------
        db_path: Path | None
            Explicit path or None to resolve default location. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes database path and verifies parent directory.
        """
        self._db_path: Path = self._resolve_db_path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def db_path(self) -> Path:
        """Return the resolved SQLite database filesystem path.

        Parameters
        ------------
        None

        Returns
        --------
            Path: Path object
                Filesystem location of SQLite database.
        """
        target: Path = self._db_path
        return target

    def _resolve_db_path(self, explicit_path: Path | None) -> Path:
        """Resolve database path from arguments, environment, or default roots.

        Parameters
        ------------
        explicit_path: Path | None
            Explicit path passed to constructor.

        Returns
        --------
            Path: Path object
                Canonical path to the SQLite documentation database.
        """
        if explicit_path is not None:
            return explicit_path

        env_path: str = os.environ.get("NEURI_DOCS_DB", "").strip()
        if env_path:
            return Path(env_path).expanduser().resolve()

        repo_root: Path = PathResolver.get_repo_root()
        default_candidate: Path = repo_root / "neuri" / "brain" / "docs.db"
        return default_candidate

    def get_connection(self) -> sqlite3.Connection:
        """Open and configure a SQLite connection with foreign keys enabled.

        Parameters
        ------------
        None

        Returns
        --------
            sqlite3.Connection: Connection object
                Configured SQLite connection.
        """
        conn: sqlite3.Connection = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def init_db(self) -> None:
        """Execute DDL script to create tables, indexes, and FTS5 triggers.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Initializes schema tables and triggers.
        """
        with self.get_connection() as conn:
            conn.executescript(DocsDBSchema.DDL_SCRIPT)

    def upsert_pipeline(self, pipeline: PipelineMetadata) -> int:
        """Insert or update a pipeline entry in the database.

        Parameters
        ------------
        pipeline: PipelineMetadata
            Pipeline metadata model to persist.

        Returns
        --------
            int: integer object
                Database row ID of the upserted pipeline.
        """
        sql: str = """
        INSERT INTO pipelines (
            name, display_name, aliases, has_commands, has_functions,
            has_documentation, description
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            display_name = excluded.display_name,
            aliases = excluded.aliases,
            has_commands = excluded.has_commands,
            has_functions = excluded.has_functions,
            has_documentation = excluded.has_documentation,
            description = excluded.description
        RETURNING id;
        """
        aliases_json: str = json.dumps(pipeline.aliases)
        with self.get_connection() as conn:
            cursor: sqlite3.Cursor = conn.execute(
                sql,
                (
                    pipeline.name.lower().strip(),
                    pipeline.display_name,
                    aliases_json,
                    1 if pipeline.has_commands else 0,
                    1 if pipeline.has_functions else 0,
                    1 if pipeline.has_documentation else 0,
                    pipeline.description,
                ),
            )
            row: sqlite3.Row | None = cursor.fetchone()
            if row is None:
                raise RuntimeError(
                    f"Failed to upsert pipeline: {pipeline.name}"
                )
            pipeline_id: int = int(row["id"])
            return pipeline_id

    def insert_doc_chunks(
        self,
        pipeline_id: int,
        pipeline_name: str,
        doc_type: DocType,
        chunks: list[DocChunkRecord],
    ) -> int:
        """Bulk insert documentation chunks for a specific pipeline and type.

        Parameters
        ------------
        pipeline_id: int
            Database identifier of target pipeline.
        pipeline_name: str
            Canonical name of target pipeline.
        doc_type: DocType
            Documentation category ('commands', 'functions', 'documentation').
        chunks: list[DocChunkRecord]
            List of parsed documentation chunks to store.

        Returns
        --------
            int: integer object
                Number of chunks successfully inserted.
        """
        delete_sql: str = """
        DELETE FROM doc_entries
        WHERE pipeline_id = ? AND doc_type = ?;
        """
        insert_sql: str = """
        INSERT INTO doc_entries (
            pipeline_id, pipeline_name, doc_type, section_title, item_name,
            content, source_file
        ) VALUES (?, ?, ?, ?, ?, ?, ?);
        """
        with self.get_connection() as conn:
            conn.execute(delete_sql, (pipeline_id, doc_type))
            data: list[tuple[int, str, str, str, str, str, str]] = [
                (
                    pipeline_id,
                    pipeline_name.lower().strip(),
                    doc_type,
                    c.section_title,
                    c.item_name,
                    c.content,
                    c.source_file,
                )
                for c in chunks
            ]
            conn.executemany(insert_sql, data)
            inserted_count: int = len(data)
            return inserted_count

    def list_pipelines(self) -> list[PipelineMetadata]:
        """Retrieve all registered neuroimaging pipelines from the database.

        Parameters
        ------------
        None

        Returns
        --------
            list[PipelineMetadata]: list object
                Alphabetical list of registered pipeline models.
        """
        sql: str = """
        SELECT name, display_name, aliases, has_commands, has_functions,
               has_documentation, description
        FROM pipelines
        ORDER BY name ASC;
        """
        with self.get_connection() as conn:
            rows: list[sqlite3.Row] = conn.execute(sql).fetchall()
            results: list[PipelineMetadata] = []
            for r in rows:
                aliases: list[str] = json.loads(str(r["aliases"]))
                meta: PipelineMetadata = PipelineMetadata(
                    name=str(r["name"]),
                    display_name=str(r["display_name"]),
                    aliases=aliases,
                    has_commands=bool(r["has_commands"]),
                    has_functions=bool(r["has_functions"]),
                    has_documentation=bool(r["has_documentation"]),
                    description=str(r["description"]),
                )
                results.append(meta)
            return results

    def resolve_pipeline_name(self, name_or_alias: str) -> str | None:
        """Resolve an arbitrary pipeline query string to its canonical name.

        Parameters
        ------------
        name_or_alias: str
            Raw input pipeline name, alias, or shorthand.

        Returns
        --------
            str | None: string or None
                Canonical pipeline name if matched, otherwise None.
        """
        cleaned: str = name_or_alias.strip().lower()
        cleaned_simple: str = re.sub(r"[-_]", "", cleaned)

        pipelines: list[PipelineMetadata] = self.list_pipelines()
        for p in pipelines:
            p_name: str = p.name.lower()
            p_simple: str = re.sub(r"[-_]", "", p_name)
            if cleaned == p_name or cleaned_simple == p_simple:
                return p.name

            for alias in p.aliases:
                a_name: str = alias.lower()
                a_simple: str = re.sub(r"[-_]", "", a_name)
                if cleaned == a_name or cleaned_simple == a_simple:
                    return p.name

        return None

    def _sanitize_fts5_query(self, query: str) -> str:
        """Sanitize raw query string for SQLite FTS5 query parser.

        Parameters
        ------------
        query: str
            Unsanitized query string.

        Returns
        --------
            str: string object
                FTS5-compatible search expression.
        """
        tokens: list[str] = re.findall(r'[a-zA-Z0-9_\-\.]+', query)
        if not tokens:
            return ""

        escaped_tokens: list[str] = []
        for token in tokens:
            clean_token: str = token.replace('"', '""')
            escaped_tokens.append(f'"{clean_token}"')

        fts_query: str = " AND ".join(escaped_tokens)
        return fts_query

    def search(
        self,
        pipeline: str,
        query: str,
        doc_type: DocType | None = None,
        limit: int = 5,
    ) -> list[DocSearchResult]:
        """Perform full-text search with BM25 ranking and LIKE fallback.

        Parameters
        ------------
        pipeline: str
            Pipeline name or alias to query.
        query: str
            Search text terms or flags.
        doc_type: DocType | None
            Documentation filter ('commands', 'functions', 'documentation').
            Defaults to None.
        limit: int
            Maximum number of result items to return. Defaults to 5.

        Returns
        --------
            list[DocSearchResult]: list object
                Ranked documentation search results.
        """
        canonical_name: str | None = self.resolve_pipeline_name(pipeline)
        if canonical_name is None:
            return []

        fts_terms: str = self._sanitize_fts5_query(query)
        fts_results: list[DocSearchResult] = []
        if fts_terms:
            fts_results = self._query_fts5(
                canonical_name=canonical_name,
                fts_terms=fts_terms,
                doc_type=doc_type,
                limit=limit,
            )

        if fts_results:
            return fts_results

        like_results: list[DocSearchResult] = self._query_like(
            canonical_name=canonical_name,
            query=query,
            doc_type=doc_type,
            limit=limit,
        )
        return like_results

    def _query_fts5(
        self,
        canonical_name: str,
        fts_terms: str,
        doc_type: DocType | None,
        limit: int,
    ) -> list[DocSearchResult]:
        """Execute FTS5 MATCH query with BM25 ranking.

        Parameters
        ------------
        canonical_name: str
            Canonical pipeline name.
        fts_terms: str
            Sanitized FTS5 search expression.
        doc_type: DocType | None
            Optional doc type filter.
        limit: int
            Max results.

        Returns
        --------
            list[DocSearchResult]: list object
                Matching search result items.
        """
        results: list[DocSearchResult] = []
        if doc_type:
            sql: str = """
            SELECT e.pipeline_name, e.doc_type, e.section_title, e.item_name,
                   e.content, bm25(doc_entries_fts) as rank
            FROM doc_entries_fts f
            JOIN doc_entries e ON f.rowid = e.id
            WHERE f.pipeline_name = ?
              AND f.doc_type = ?
              AND doc_entries_fts MATCH ?
            ORDER BY rank ASC
            LIMIT ?;
            """
            params: tuple[Any, ...] = (
                canonical_name,
                doc_type,
                fts_terms,
                limit,
            )
        else:
            sql = """
            SELECT e.pipeline_name, e.doc_type, e.section_title, e.item_name,
                   e.content, bm25(doc_entries_fts) as rank
            FROM doc_entries_fts f
            JOIN doc_entries e ON f.rowid = e.id
            WHERE f.pipeline_name = ?
              AND doc_entries_fts MATCH ?
            ORDER BY rank ASC
            LIMIT ?;
            """
            params = (canonical_name, fts_terms, limit)

        try:
            with self.get_connection() as conn:
                rows: list[sqlite3.Row] = conn.execute(sql, params).fetchall()
                for r in rows:
                    item: DocSearchResult = DocSearchResult(
                        pipeline=str(r["pipeline_name"]),
                        doc_type=cast(DocType, str(r["doc_type"])),
                        section_title=str(r["section_title"]),
                        item_name=str(r["item_name"]),
                        content=str(r["content"]),
                        score=float(r["rank"]),
                    )
                    results.append(item)
        except sqlite3.OperationalError:
            results = []

        return results

    def _query_like(
        self,
        canonical_name: str,
        query: str,
        doc_type: DocType | None,
        limit: int,
    ) -> list[DocSearchResult]:
        """Execute fallback substring LIKE query when FTS yields no hits.

        Parameters
        ------------
        canonical_name: str
            Canonical pipeline name.
        query: str
            Search query string.
        doc_type: DocType | None
            Optional doc type filter.
        limit: int
            Max results.

        Returns
        --------
            list[DocSearchResult]: list object
                Matching search result items.
        """
        results: list[DocSearchResult] = []
        like_pattern: str = f"%{query.strip()}%"

        if doc_type:
            sql: str = """
            SELECT pipeline_name, doc_type, section_title, item_name, content
            FROM doc_entries
            WHERE pipeline_name = ?
              AND doc_type = ?
              AND (item_name LIKE ? OR section_title LIKE ? OR content LIKE ?)
            LIMIT ?;
            """
            params: tuple[Any, ...] = (
                canonical_name,
                doc_type,
                like_pattern,
                like_pattern,
                like_pattern,
                limit,
            )
        else:
            sql = """
            SELECT pipeline_name, doc_type, section_title, item_name, content
            FROM doc_entries
            WHERE pipeline_name = ?
              AND (item_name LIKE ? OR section_title LIKE ? OR content LIKE ?)
            LIMIT ?;
            """
            params = (
                canonical_name,
                like_pattern,
                like_pattern,
                like_pattern,
                limit,
            )

        with self.get_connection() as conn:
            rows: list[sqlite3.Row] = conn.execute(sql, params).fetchall()
            for r in rows:
                item: DocSearchResult = DocSearchResult(
                    pipeline=str(r["pipeline_name"]),
                    doc_type=cast(DocType, str(r["doc_type"])),
                    section_title=str(r["section_title"]),
                    item_name=str(r["item_name"]),
                    content=str(r["content"]),
                    score=0.0,
                )
                results.append(item)

        return results


__all__: list[str] = [
    "DocsRepository",
]
