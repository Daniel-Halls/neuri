# Investigation Report: Milestone 2 — SQLite DDL Schemas, WAL Mode, Foreign Keys & Connection Management

**Role:** Explorer M2-1 (DDL & WAL)  
**Date:** 2026-10-25T16:19:00Z  
**Target Module:** `src/neuri/core/blackboard.py`  
**Working Directory:** `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m2_1/`

---

## 1. Observation

### 1.1 Direct Observations from Codebase & Specifications

1. **Original User Request & Architecture Plan:**
   - `technical_documenation/NEURI_ARCHITECTURE_AND_IMPLEMENTATION_PLAN.md` (lines 366-376) states:
     > "The local SQLite database runs in `WAL` (Write-Ahead Logging) mode for concurrent multi-agent reads/writes and contains 7 core tables:
     > 1. `workflows`: `workflow_id (PK)`, `user_prompt`, `status`, `total_tokens`, `total_cost_usd`, `created_at`, `updated_at`.
     > 2. `task_nodes`: `node_id (PK)`, `workflow_id (FK)`, `agent_role`, `harness_id`, `state`, `attempt`, `max_retries`, `envelope_json`, `summary_result`, `diagnostic_feedback`, `started_at`, `completed_at`.
     > 3. `task_edges`: `workflow_id (FK)`, `parent_node_id (FK)`, `child_node_id (FK)` (defines the DAG execution order).
     > 4. `remote_artifacts`: `artifact_id (PK)`, `workflow_id (FK)`, `uri (UNIQUE)`, `host`, `modality`, `space`, `header_json`, `created_by_node (FK)`, `created_at`.
     > 5. `remote_jobs`: `job_id (PK)`, `node_id (FK)`, `host`, `scheduler_type (slurm|tmux)`, `remote_scheduler_id`, `status_uri`, `state`, `submitted_at`, `reconciled_at`.
     > 6. `telemetry_events`: `event_id (PK)`, `workflow_id (FK)`, `node_id (FK)`, `harness_id`, `event_type`, `payload_json`, `timestamp`.
     > 7. `citations_ledger`: `citation_key (PK)`, `doi`, `pmid`, `title`, `authors_json`, `year`, `bibtex_entry`, `verified_at` (enforces the Scientific Writer's anti-hallucination rule)."

2. **Task Assignment (`DISPATCH.md` lines 10-22):**
   - Configures SQLite WAL mode via:
     - `PRAGMA journal_mode=WAL;`
     - `PRAGMA foreign_keys=ON;`
     - `PRAGMA busy_timeout=5000;`
     - `PRAGMA synchronous=NORMAL;`
   - Explicitly enumerates the 7 core tables and target column sets:
     - `workflows (workflow_id, prompt, status, created_at, updated_at, total_tokens, estimated_cost_usd)`
     - `task_nodes (node_id, workflow_id, agent_role, harness_id, state, envelope_json, diagnostic_feedback_json, created_at, updated_at, completed_at)`
     - `task_edges (workflow_id, parent_node_id, child_node_id)`
     - `remote_artifacts (uri, workflow_id, node_id, host, posix_path, modality, space, header_json, sha256, created_at)`
     - `remote_jobs (job_id, node_id, host, scheduler_type, scheduler_job_id, status_uri, created_at, updated_at)`
     - `telemetry_events (event_id, workflow_id, node_id, timestamp, event_type, thinking_text, input_tokens, output_tokens, cost_usd, tool_name, tool_status, payload_json)`
     - `citations_ledger (citation_key, doi, pmid, title, authors, year, bibtex, verified, created_at)`

3. **Core Pydantic Contracts (`src/neuri/core/schemas.py`):**
   - `TaskState` (lines 470-495): Enum with 9 states: `PENDING`, `PREFLIGHT_CHECK`, `RUNNING`, `QA_REVIEW`, `RETRYING`, `WAITING_OPERATOR`, `COMPLETED`, `FAILED`, `CANCELLED`.
   - `TaskNode` (lines 913-1004): Fields `node_id: str`, `workflow_id: str`, `agent_role: str`, `harness_id: str`, `state: TaskState`, `attempt: int = 0`, `max_retries: int = 2`, `envelope: NeuriTaskEnvelope | None = None`, `summary_result: str | None = None`, `diagnostic_feedback: list[str] = []`, `started_at: datetime | None = None`, `completed_at: datetime | None = None`.
   - `TaskEdge` (lines 1113-1168): Fields `workflow_id: str`, `parent_node_id: str`, `child_node_id: str`, with self-loop validation (`parent_node_id != child_node_id`).
   - `RemoteArtifact` (lines 308-398): Fields `artifact_id: str`, `uri: str` (`host:///posix/path`), `host: str`, `posix_path: str`, `modality: ModalityType`, `space: str | None`, `bids_entities: dict[str, str]`, `sha256_header: str`, `size_bytes: int`, `header_summary: SanitizedNeuroHeader`, `created_by_node: str | None`, `created_at: datetime`.
   - `TelemetryEvent` (lines 1170-1305): Fields `event_id: str`, `workflow_id: str`, `node_id: str`, `harness_id: str`, `timestamp: datetime`, `event_type: Literal["thinking_delta", "token_usage", "tool_lifecycle", "circuit_breaker"]`, `thinking_text: str | None`, `input_tokens: int`, `cached_tokens: int`, `reasoning_tokens: int`, `output_tokens: int`, `estimated_cost_usd: float`, `tool_name: str | None`, `tool_host: str | None`, `tool_status: Literal["started", "completed", "failed"] | None`, `duration_ms: int | None`, `breaker_reason: str | None`.

4. **Integration with Two-Tier Config Loader (`src/neuri/core/config.py` lines 674-685):**
   - `WorkspaceInitializer._init_sqlite_wal(db_path: Path)` calls:
     ```python
     try:
         from neuri.core.blackboard import Blackboard
         Blackboard(db_path)
     except (ImportError, Exception):
         conn: sqlite3.Connection = sqlite3.connect(str(db_path))
         try:
             conn.execute("PRAGMA journal_mode=WAL;")
             conn.execute("PRAGMA foreign_keys=ON;")
             conn.commit()
         finally:
             conn.close()
     ```
   - Therefore, `Blackboard(db_path)` must instantiate and auto-initialize the schema if tables do not exist.

5. **Universal Python Standards AST Validator (`tests/unit/test_standards_compliance.py`):**
   - AST validator enforces:
     - PascalCase class names, snake_case function/method names.
     - Full type annotations on all parameters and returns.
     - Mandatory docstrings with `Parameters\s*\n\s*-{3,}` and `Returns\s*\n\s*-{3,}` headers.
     - Zero module-level global variables (`check_zero_globals`, lines 266-343): all SQL strings and constants must reside inside classes as class attributes.
     - Single return statement per function returning a single typed variable.
     - Line length limit <= 88 characters.

---

## 2. Logic Chain

### 2.1 Schema Reconciliation & Completeness
- From Observation 1.1, 1.2, and 1.3, the specifications for the 7 tables share strong semantic continuity, but exhibit minor alias variations (`prompt` vs `user_prompt`, `artifact_id` + `uri`, `sha256` vs `sha256_header`, `node_id` vs `created_by_node`, `cost_usd` vs `estimated_cost_usd`).
- By defining standard SQL column names matching DISPATCH.md and augmenting with defaults for Pydantic model attributes:
  1. `workflows`: Table uses `prompt TEXT NOT NULL`, `status TEXT NOT NULL`, `created_at TEXT`, `updated_at TEXT`, `total_tokens INTEGER`, `estimated_cost_usd REAL`.
  2. `task_nodes`: Table uses `node_id TEXT PRIMARY KEY`, `workflow_id TEXT REFERENCES workflows(workflow_id) ON DELETE CASCADE`, `agent_role TEXT`, `harness_id TEXT`, `state TEXT`, `attempt INTEGER DEFAULT 0`, `max_retries INTEGER DEFAULT 2`, `envelope_json TEXT`, `summary_result TEXT`, `diagnostic_feedback_json TEXT DEFAULT '[]'`, `created_at TEXT`, `updated_at TEXT`, `started_at TEXT`, `completed_at TEXT`. This aligns both with DISPATCH.md and with Pydantic model `TaskNode`.
  3. `task_edges`: Composite primary key `(workflow_id, parent_node_id, child_node_id)` with foreign keys to `task_nodes(node_id) ON DELETE CASCADE` and `workflows(workflow_id) ON DELETE CASCADE`. CHECK constraint `parent_node_id != child_node_id` enforces acyclic self-loop prevention at the database level.
  4. `remote_artifacts`: `artifact_id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16))))`, `uri TEXT NOT NULL UNIQUE`, `workflow_id TEXT REFERENCES workflows(workflow_id) ON DELETE CASCADE`, `node_id TEXT REFERENCES task_nodes(node_id) ON DELETE SET NULL`, `host TEXT`, `posix_path TEXT`, `modality TEXT`, `space TEXT`, `size_bytes INTEGER DEFAULT 0`, `sha256 TEXT`, `header_json TEXT`, `bids_entities_json TEXT DEFAULT '{}'`, `created_at TEXT`. This accommodates both URI-based lookups, POSIX uniqueness, and Pydantic `RemoteArtifact` instantiation.
  5. `remote_jobs`: `job_id TEXT PRIMARY KEY`, `node_id TEXT REFERENCES task_nodes(node_id) ON DELETE CASCADE`, `host TEXT`, `scheduler_type TEXT CHECK (scheduler_type IN ('slurm', 'tmux'))`, `scheduler_job_id TEXT`, `status_uri TEXT`, `state TEXT DEFAULT 'SUBMITTED'`, `created_at TEXT`, `updated_at TEXT`.
  6. `telemetry_events`: `event_id TEXT PRIMARY KEY`, `workflow_id TEXT REFERENCES workflows(workflow_id) ON DELETE CASCADE`, `node_id TEXT REFERENCES task_nodes(node_id) ON DELETE CASCADE`, `harness_id TEXT DEFAULT 'unknown'`, `timestamp TEXT`, `event_type TEXT CHECK (event_type IN ('thinking_delta', 'token_usage', 'tool_lifecycle', 'circuit_breaker'))`, `thinking_text TEXT`, `input_tokens INTEGER DEFAULT 0`, `output_tokens INTEGER DEFAULT 0`, `cost_usd REAL DEFAULT 0.0`, `tool_name TEXT`, `tool_status TEXT CHECK (tool_status IS NULL OR tool_status IN ('started', 'completed', 'failed'))`, `payload_json TEXT DEFAULT '{}'`.
  7. `citations_ledger`: `citation_key TEXT PRIMARY KEY`, `doi TEXT`, `pmid TEXT`, `title TEXT`, `authors TEXT`, `year INTEGER CHECK (year >= 1800 AND year <= 2100)`, `bibtex TEXT`, `verified INTEGER DEFAULT 1 CHECK (verified IN (0, 1))`, `created_at TEXT`.

### 2.2 WAL Mode & Connection Pragmas
- In SQLite, while `PRAGMA journal_mode=WAL;` is persisted in the database file header, `PRAGMA foreign_keys=ON;`, `PRAGMA busy_timeout=5000;`, and `PRAGMA synchronous=NORMAL;` are connection-local and MUST be executed on every new connection opened.
- `PRAGMA busy_timeout=5000;` prevents concurrency crashes when multiple threads or processes access the Blackboard simultaneously, allowing SQLite to wait up to 5 seconds before raising `sqlite3.OperationalError: database is locked`.
- `PRAGMA synchronous=NORMAL;` in conjunction with `WAL` reduces disk write wear and eliminates synchronous fsync bottlenecks during rapid telemetry logging without risking data corruption.

### 2.3 Index Optimization for Downstream Queries
- Downstream Explorer M2-2 requires `get_ready_nodes(workflow_id: str)`:
  - Query filters `task_nodes` by `workflow_id` and `state = 'PENDING'`.
  - Joins with `task_edges` on `task_edges.child_node_id = task_nodes.node_id`.
  - Asserts all parent nodes in `task_nodes` have `state = 'COMPLETED'`.
  - To make this sub-millisecond even with hundreds of nodes, we define:
    - Composite index `idx_task_nodes_workflow_state` on `task_nodes (workflow_id, state)`.
    - Composite index `idx_task_edges_workflow_child` on `task_edges (workflow_id, child_node_id)`.
    - Composite index `idx_task_edges_workflow_parent` on `task_edges (workflow_id, parent_node_id)`.
- Downstream Explorer M2-3 requires `export_provenance(workflow_id: str)`:
  - Query extracts all artifacts and jobs by `workflow_id` or `node_id`.
  - Indexes `idx_remote_artifacts_workflow_id`, `idx_remote_artifacts_node_id`, and `idx_remote_jobs_node_id` provide indexed lookups.

### 2.4 Standards Compliance (Zero Globals, Full Typing, Custom Docstrings)
- From Observation 1.5, to comply with `tests/unit/test_standards_compliance.py`, all DDL statements and SQL fragments must be class attributes within a dedicated container class (e.g. `BlackboardSchema`).
- No module-level `CREATE_TABLE_SQL = ...` is permitted.

---

## 3. Caveats

1. **In-Memory vs File-Based SQLite:**
   - In SQLite, `:memory:` databases do not support true multi-process WAL mode (in-memory WAL mode falls back to memory rollback journal). However, for unit tests using `sqlite3.connect(":memory:")`, executing `PRAGMA journal_mode=WAL;` returns `memory` and does not raise an error. Blackboard handles both disk and memory modes transparently.
2. **Foreign Key Cascade Deletions:**
   - Deleting a workflow cascade-deletes all associated `task_nodes`, `task_edges`, `remote_artifacts`, and `telemetry_events`. In contrast, deleting a `task_node` sets `remote_artifacts.node_id` to `NULL` (`ON DELETE SET NULL`) so that scientific datasets and generated artifacts are never accidentally detached or dropped if an intermediate execution node record is cleaned up.
3. **No Code Modification Rule:**
   - As an explorer agent, this report provides exact, copy-paste-ready Python specifications and class definitions for the implementer agent. No source files have been modified.

---

## 4. Conclusion & Specification

### 4.1 SQLite DDL Specifications (Class `BlackboardSchema`)

```python
class BlackboardSchema:
    """Encapsulates SQLite DDL schemas, pragmas, and index specifications.

    Provides constant SQL statements and table definitions for the 7 core
    relational tables in the Neuri Blackboard state engine, enforcing zero
    module-level global variables.
    """

    PRAGMA_WAL: str = "PRAGMA journal_mode=WAL;"
    PRAGMA_FOREIGN_KEYS: str = "PRAGMA foreign_keys=ON;"
    PRAGMA_BUSY_TIMEOUT: str = "PRAGMA busy_timeout=5000;"
    PRAGMA_SYNCHRONOUS: str = "PRAGMA synchronous=NORMAL;"

    CREATE_WORKFLOWS_TABLE: str = """
    CREATE TABLE IF NOT EXISTS workflows (
        workflow_id TEXT PRIMARY KEY,
        prompt TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN (
            'PENDING', 'RUNNING', 'COMPLETED', 'FAILED',
            'CANCELLED', 'WAITING_OPERATOR'
        )),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        total_tokens INTEGER NOT NULL DEFAULT 0 CHECK (total_tokens >= 0),
        estimated_cost_usd REAL NOT NULL DEFAULT 0.0 CHECK (estimated_cost_usd >= 0.0)
    );
    """

    CREATE_TASK_NODES_TABLE: str = """
    CREATE TABLE IF NOT EXISTS task_nodes (
        node_id TEXT PRIMARY KEY,
        workflow_id TEXT NOT NULL REFERENCES workflows(workflow_id) ON DELETE CASCADE,
        agent_role TEXT NOT NULL,
        harness_id TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'PENDING' CHECK (state IN (
            'PENDING', 'PREFLIGHT_CHECK', 'RUNNING', 'QA_REVIEW',
            'RETRYING', 'WAITING_OPERATOR', 'COMPLETED', 'FAILED', 'CANCELLED'
        )),
        attempt INTEGER NOT NULL DEFAULT 0 CHECK (attempt >= 0),
        max_retries INTEGER NOT NULL DEFAULT 2 CHECK (max_retries >= 0),
        envelope_json TEXT,
        summary_result TEXT,
        diagnostic_feedback_json TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        started_at TEXT,
        completed_at TEXT
    );
    """

    CREATE_TASK_EDGES_TABLE: str = """
    CREATE TABLE IF NOT EXISTS task_edges (
        workflow_id TEXT NOT NULL REFERENCES workflows(workflow_id) ON DELETE CASCADE,
        parent_node_id TEXT NOT NULL REFERENCES task_nodes(node_id) ON DELETE CASCADE,
        child_node_id TEXT NOT NULL REFERENCES task_nodes(node_id) ON DELETE CASCADE,
        PRIMARY KEY (workflow_id, parent_node_id, child_node_id),
        CHECK (parent_node_id != child_node_id)
    );
    """

    CREATE_REMOTE_ARTIFACTS_TABLE: str = """
    CREATE TABLE IF NOT EXISTS remote_artifacts (
        artifact_id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
        uri TEXT NOT NULL UNIQUE,
        workflow_id TEXT NOT NULL REFERENCES workflows(workflow_id) ON DELETE CASCADE,
        node_id TEXT REFERENCES task_nodes(node_id) ON DELETE SET NULL,
        host TEXT NOT NULL,
        posix_path TEXT NOT NULL,
        modality TEXT NOT NULL,
        space TEXT,
        size_bytes INTEGER NOT NULL DEFAULT 0 CHECK (size_bytes >= 0),
        sha256 TEXT NOT NULL,
        header_json TEXT NOT NULL,
        bids_entities_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL
    );
    """

    CREATE_REMOTE_JOBS_TABLE: str = """
    CREATE TABLE IF NOT EXISTS remote_jobs (
        job_id TEXT PRIMARY KEY,
        node_id TEXT NOT NULL REFERENCES task_nodes(node_id) ON DELETE CASCADE,
        host TEXT NOT NULL,
        scheduler_type TEXT NOT NULL CHECK (scheduler_type IN ('slurm', 'tmux')),
        scheduler_job_id TEXT NOT NULL,
        status_uri TEXT,
        state TEXT NOT NULL DEFAULT 'SUBMITTED' CHECK (state IN (
            'SUBMITTED', 'PENDING', 'RUNNING', 'COMPLETED',
            'FAILED', 'CANCELLED'
        )),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """

    CREATE_TELEMETRY_EVENTS_TABLE: str = """
    CREATE TABLE IF NOT EXISTS telemetry_events (
        event_id TEXT PRIMARY KEY,
        workflow_id TEXT NOT NULL REFERENCES workflows(workflow_id) ON DELETE CASCADE,
        node_id TEXT NOT NULL REFERENCES task_nodes(node_id) ON DELETE CASCADE,
        harness_id TEXT NOT NULL DEFAULT 'unknown',
        timestamp TEXT NOT NULL,
        event_type TEXT NOT NULL CHECK (event_type IN (
            'thinking_delta', 'token_usage', 'tool_lifecycle', 'circuit_breaker'
        )),
        thinking_text TEXT,
        input_tokens INTEGER NOT NULL DEFAULT 0 CHECK (input_tokens >= 0),
        output_tokens INTEGER NOT NULL DEFAULT 0 CHECK (output_tokens >= 0),
        cost_usd REAL NOT NULL DEFAULT 0.0 CHECK (cost_usd >= 0.0),
        tool_name TEXT,
        tool_status TEXT CHECK (tool_status IS NULL OR tool_status IN (
            'started', 'completed', 'failed'
        )),
        payload_json TEXT NOT NULL DEFAULT '{}'
    );
    """

    CREATE_CITATIONS_LEDGER_TABLE: str = """
    CREATE TABLE IF NOT EXISTS citations_ledger (
        citation_key TEXT PRIMARY KEY,
        doi TEXT,
        pmid TEXT,
        title TEXT NOT NULL,
        authors TEXT NOT NULL,
        year INTEGER NOT NULL CHECK (year >= 1800 AND year <= 2100),
        bibtex TEXT NOT NULL,
        verified INTEGER NOT NULL DEFAULT 1 CHECK (verified IN (0, 1)),
        created_at TEXT NOT NULL
    );
    """

    INDEXES: tuple[str, ...] = (
        # Workflows indexes
        "CREATE INDEX IF NOT EXISTS idx_workflows_status ON workflows (status);",
        "CREATE INDEX IF NOT EXISTS idx_workflows_created ON workflows (created_at DESC);",
        # Task nodes indexes
        "CREATE INDEX IF NOT EXISTS idx_task_nodes_wf ON task_nodes (workflow_id);",
        "CREATE INDEX IF NOT EXISTS idx_task_nodes_wf_state ON task_nodes (workflow_id, state);",
        "CREATE INDEX IF NOT EXISTS idx_task_nodes_state ON task_nodes (state);",
        "CREATE INDEX IF NOT EXISTS idx_task_nodes_harness ON task_nodes (harness_id);",
        # Task edges indexes (critical for get_ready_nodes)
        "CREATE INDEX IF NOT EXISTS idx_task_edges_wf_child ON task_edges (workflow_id, child_node_id);",
        "CREATE INDEX IF NOT EXISTS idx_task_edges_wf_parent ON task_edges (workflow_id, parent_node_id);",
        # Remote artifacts indexes
        "CREATE INDEX IF NOT EXISTS idx_artifacts_wf ON remote_artifacts (workflow_id);",
        "CREATE INDEX IF NOT EXISTS idx_artifacts_node ON remote_artifacts (node_id);",
        "CREATE INDEX IF NOT EXISTS idx_artifacts_modality ON remote_artifacts (modality);",
        "CREATE INDEX IF NOT EXISTS idx_artifacts_host_path ON remote_artifacts (host, posix_path);",
        # Remote jobs indexes
        "CREATE INDEX IF NOT EXISTS idx_jobs_node ON remote_jobs (node_id);",
        "CREATE INDEX IF NOT EXISTS idx_jobs_state ON remote_jobs (state);",
        "CREATE INDEX IF NOT EXISTS idx_jobs_scheduler ON remote_jobs (scheduler_type, scheduler_job_id);",
        # Telemetry events indexes
        "CREATE INDEX IF NOT EXISTS idx_telemetry_wf ON telemetry_events (workflow_id);",
        "CREATE INDEX IF NOT EXISTS idx_telemetry_node ON telemetry_events (node_id);",
        "CREATE INDEX IF NOT EXISTS idx_telemetry_type ON telemetry_events (event_type);",
        "CREATE INDEX IF NOT EXISTS idx_telemetry_ts ON telemetry_events (timestamp);",
        "CREATE INDEX IF NOT EXISTS idx_telemetry_tool ON telemetry_events (tool_name, tool_status);",
        # Citations ledger indexes
        "CREATE INDEX IF NOT EXISTS idx_citations_doi ON citations_ledger (doi) WHERE doi IS NOT NULL;",
        "CREATE INDEX IF NOT EXISTS idx_citations_pmid ON citations_ledger (pmid) WHERE pmid IS NOT NULL;",
        "CREATE INDEX IF NOT EXISTS idx_citations_verified ON citations_ledger (verified);",
    )
```

---

### 4.2 Connection Management & Class Architecture

```python
"""Neuri Core Blackboard State Engine.

Provides SQLite WAL persistent blackboard storage for workflows, DAG task nodes,
directed dependency edges, remote artifact pointers, asynchronous jobs,
streaming telemetry events, and verified citations ledger.
"""

from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any

from neuri.core.schemas import (
    ModalityType,
    NeuriTaskEnvelope,
    RemoteArtifact,
    SanitizedNeuroHeader,
    TaskEdge,
    TaskNode,
    TaskState,
    TelemetryEvent,
)


class BlackboardError(Exception):
    """Exception raised for errors in SQLite Blackboard state operations.

    Parameters
    ------------
    message: str
        Descriptive explanation of the database error condition.

    Returns
    --------
        BlackboardError: BlackboardError instance
            Initialized exception object.
    """

    def __init__(self, message: str) -> None:
        """Initialize Blackboard exception.

        Parameters
        ------------
        message: str
            Descriptive error message.

        Returns
        --------
            None: NoneType object
                Initializes exception state.
        """
        super().__init__(message)


class Blackboard:
    """SQLite WAL-backed persistent blackboard coordinating multi-agent state.

    Manages concurrent connections, schema initialization, atomic DAG queries,
    state transitions, and provenance tracking.

    Parameters
    ------------
    db_path: Path | str
        Filesystem path to the SQLite database file or ':memory:'.
    timeout_seconds: float
        Lock acquisition busy timeout in seconds. Defaults to 5.0.

    Returns
    --------
        Blackboard: Blackboard instance
            Constructed state engine instance.
    """

    def __init__(
        self,
        db_path: Path | str = Path(".neuri/state.db"),
        timeout_seconds: float = 5.0,
    ) -> None:
        """Initialize blackboard connection manager and ensure schema exists.

        Parameters
        ------------
        db_path: Path | str
            Path to the SQLite database file. Defaults to .neuri/state.db.
        timeout_seconds: float
            Busy timeout in seconds. Defaults to 5.0.

        Returns
        --------
            None: NoneType object
                Initializes instance and establishes schema.
        """
        if isinstance(db_path, str) and db_path != ":memory:":
            self._db_path: Path = Path(db_path)
            self._is_memory: bool = False
        elif isinstance(db_path, Path):
            self._db_path = db_path
            self._is_memory = False
        else:
            self._db_path = Path(":memory:")
            self._is_memory = True

        self._timeout: float = timeout_seconds
        self._shared_conn: sqlite3.Connection | None = None

        if self._is_memory:
            # Persistent connection for in-memory databases to retain state
            self._shared_conn = self._create_connection()
            self._init_schema(self._shared_conn)
        else:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            with self.connection() as conn:
                self._init_schema(conn)

    @property
    def db_path(self) -> Path:
        """Return the configured database path.

        Parameters
        ------------
        None

        Returns
        --------
            Path: Path object
                Database file path or :memory:.
        """
        result: Path = self._db_path
        return result

    def _create_connection(self) -> sqlite3.Connection:
        """Create and configure a new SQLite connection with mandatory pragmas.

        Parameters
        ------------
        None

        Returns
        --------
            sqlite3.Connection: Connection object
                Configured SQLite connection in WAL mode with foreign keys enabled.
        """
        conn_str: str = ":memory:" if self._is_memory else str(self._db_path)
        conn: sqlite3.Connection = sqlite3.connect(
            conn_str,
            timeout=self._timeout,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row

        # Execute mandatory pragmas
        conn.execute(BlackboardSchema.PRAGMA_WAL)
        conn.execute(BlackboardSchema.PRAGMA_FOREIGN_KEYS)
        conn.execute(BlackboardSchema.PRAGMA_BUSY_TIMEOUT)
        conn.execute(BlackboardSchema.PRAGMA_SYNCHRONOUS)
        return conn

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Provide a contextual database connection with automatic commit and rollback.

        Parameters
        ------------
        None

        Returns
        --------
            Generator[sqlite3.Connection, None, None]: context manager generator
                Yields configured connection inside transaction scope.
        """
        conn: sqlite3.Connection
        if self._shared_conn is not None:
            conn = self._shared_conn
            with conn:
                yield conn
        else:
            conn = self._create_connection()
            try:
                with conn:
                    yield conn
            finally:
                conn.close()

    def _init_schema(self, conn: sqlite3.Connection) -> None:
        """Initialize all 7 tables and supporting indexes if they do not exist.

        Parameters
        ------------
        conn: sqlite3.Connection
            Active SQLite connection.

        Returns
        --------
            None: NoneType object
                Executes DDL statements.
        """
        tables: tuple[str, ...] = (
            BlackboardSchema.CREATE_WORKFLOWS_TABLE,
            BlackboardSchema.CREATE_TASK_NODES_TABLE,
            BlackboardSchema.CREATE_TASK_EDGES_TABLE,
            BlackboardSchema.CREATE_REMOTE_ARTIFACTS_TABLE,
            BlackboardSchema.CREATE_REMOTE_JOBS_TABLE,
            BlackboardSchema.CREATE_TELEMETRY_EVENTS_TABLE,
            BlackboardSchema.CREATE_CITATIONS_LEDGER_TABLE,
        )
        for ddl in tables:
            conn.execute(ddl)
        for idx in BlackboardSchema.INDEXES:
            conn.execute(idx)

    def verify_wal_mode(self) -> bool:
        """Verify that the database is running with WAL journal mode.

        Parameters
        ------------
        None

        Returns
        --------
            bool: boolean object
                True if journal_mode is 'wal' or 'memory' (for in-memory dbs).
        """
        with self.connection() as conn:
            cur: sqlite3.Cursor = conn.cursor()
            cur.execute("PRAGMA journal_mode;")
            row: Any = cur.fetchone()
            mode: str = str(row[0]).lower() if row else ""
            is_wal: bool = mode in ("wal", "memory")
            return is_wal

    def verify_foreign_keys_enabled(self) -> bool:
        """Verify that foreign key enforcement is active on connections.

        Parameters
        ------------
        None

        Returns
        --------
            bool: boolean object
                True if foreign_keys pragma is enabled (1).
        """
        with self.connection() as conn:
            cur: sqlite3.Cursor = conn.cursor()
            cur.execute("PRAGMA foreign_keys;")
            row: Any = cur.fetchone()
            enabled: bool = bool(row[0]) if row else False
            return enabled

    def close(self) -> None:
        """Close any shared connections and release resources.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Closes connection.
        """
        if self._shared_conn is not None:
            self._shared_conn.close()
            self._shared_conn = None
```

---

## 5. Verification Method

### 5.1 Verification Checklist for Downstream Implementer

1. **WAL Mode Verification:**
   ```python
   bb = Blackboard(tmp_path / "state.db")
   assert bb.verify_wal_mode() is True
   ```
2. **Foreign Key Enforcement Verification:**
   - Attempting to insert a `task_node` referencing a non-existent `workflow_id` must immediately raise `sqlite3.IntegrityError: FOREIGN KEY constraint failed`.
   - Attempting to insert a self-loop into `task_edges` (`parent_node_id == child_node_id`) must raise `sqlite3.IntegrityError: CHECK constraint failed`.
3. **Table & Index Inspection:**
   - Execute query `SELECT count(*) FROM sqlite_master WHERE type='table';` to confirm all 7 core tables are created.
   - Execute query `SELECT count(*) FROM sqlite_master WHERE type='index';` to confirm all performance indexes are registered.
4. **AST Standards Compliance:**
   - Run:
     ```bash
     uv run pytest tests/unit/test_standards_compliance.py -v
     ```
   - Must pass with 0 violations (no module globals, 100% docstrings with Parameters/Returns headers, type annotations, snake_case/PascalCase naming).

### 5.2 Test Invalidation Conditions
- If any table creation omits foreign key constraints or check constraints.
- If `PRAGMA foreign_keys=ON;` is omitted from any newly opened connection.
- If DDL strings are defined at module level instead of within `BlackboardSchema`.
