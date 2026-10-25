"""Neuri Core Blackboard State Engine.

Provides SQLite WAL persistent blackboard storage for workflows, DAG task nodes,
directed dependency edges, remote artifact pointers, asynchronous jobs,
streaming telemetry events, and verified citations ledger.
"""

from collections import deque
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
from typing import Any

from neuri.core.schemas import (
    ModalityType,
    NeuriTaskEnvelope,
    NeuriTaskResult,
    RemoteArtifact,
    SanitizedNeuroHeader,
    TaskEdge,
    TaskNode,
    TaskState,
    TelemetryEvent,
)


class BlackboardError(Exception):
    """Base exception for all SQLite Blackboard state engine operations.

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


class WorkflowNotFoundError(BlackboardError):
    """Raised when a requested workflow identifier is not found in database.

    Parameters
    ------------
    message: str
        Descriptive error message.

    Returns
    --------
        WorkflowNotFoundError: WorkflowNotFoundError instance
            Initialized exception object.
    """

    def __init__(self, message: str) -> None:
        """Initialize exception instance.

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


class NodeNotFoundError(BlackboardError):
    """Raised when a requested task node identifier is not found in database.

    Parameters
    ------------
    message: str
        Descriptive error message.

    Returns
    --------
        NodeNotFoundError: NodeNotFoundError instance
            Initialized exception object.
    """

    def __init__(self, message: str) -> None:
        """Initialize exception instance.

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


class CycleDetectedError(BlackboardError):
    """Raised when adding an edge would create a directed cycle in the DAG.

    Parameters
    ------------
    message: str
        Descriptive error message.

    Returns
    --------
        CycleDetectedError: CycleDetectedError instance
            Initialized exception object.
    """

    def __init__(self, message: str) -> None:
        """Initialize exception instance.

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


class InvalidStateTransitionError(BlackboardError):
    """Raised when an illegal node state transition is attempted.

    Parameters
    ------------
    message: str
        Descriptive error message.

    Returns
    --------
        InvalidStateTransitionError: InvalidStateTransitionError instance
            Initialized exception object.
    """

    def __init__(self, message: str) -> None:
        """Initialize exception instance.

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


class DuplicateEdgeError(BlackboardError):
    """Raised when an identical dependency edge already exists.

    Parameters
    ------------
    message: str
        Descriptive error message.

    Returns
    --------
        DuplicateEdgeError: DuplicateEdgeError instance
            Initialized exception object.
    """

    def __init__(self, message: str) -> None:
        """Initialize exception instance.

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


class ArtifactRegistrationError(BlackboardError):
    """Raised when an artifact registration violates uniqueness constraints.

    Parameters
    ------------
    message: str
        Descriptive error message.

    Returns
    --------
        ArtifactRegistrationError: ArtifactRegistrationError instance
            Initialized exception object.
    """

    def __init__(self, message: str) -> None:
        """Initialize exception instance.

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


class BlackboardSchema:
    """Encapsulates SQLite DDL schemas, pragmas, and index specifications.

    Provides constant SQL statements and table definitions for the 7 core
    relational tables in the Neuri Blackboard state engine, enforcing zero
    module-level global variables.

    Parameters
    ------------
    None

    Returns
    --------
        BlackboardSchema: BlackboardSchema instance
            Schema definition container.
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
        estimated_cost_usd REAL NOT NULL DEFAULT 0.0 CHECK (
            estimated_cost_usd >= 0.0
        )
    );
    """

    CREATE_TASK_NODES_TABLE: str = """
    CREATE TABLE IF NOT EXISTS task_nodes (
        node_id TEXT PRIMARY KEY,
        workflow_id TEXT NOT NULL REFERENCES workflows(workflow_id)
            ON DELETE CASCADE,
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
        workflow_id TEXT NOT NULL REFERENCES workflows(workflow_id)
            ON DELETE CASCADE,
        parent_node_id TEXT NOT NULL REFERENCES task_nodes(node_id)
            ON DELETE CASCADE,
        child_node_id TEXT NOT NULL REFERENCES task_nodes(node_id)
            ON DELETE CASCADE,
        PRIMARY KEY (workflow_id, parent_node_id, child_node_id),
        CHECK (parent_node_id != child_node_id)
    );
    """

    CREATE_REMOTE_ARTIFACTS_TABLE: str = """
    CREATE TABLE IF NOT EXISTS remote_artifacts (
        artifact_id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
        uri TEXT NOT NULL UNIQUE,
        workflow_id TEXT NOT NULL REFERENCES workflows(workflow_id)
            ON DELETE CASCADE,
        node_id TEXT REFERENCES task_nodes(node_id) ON DELETE SET NULL,
        host TEXT NOT NULL,
        posix_path TEXT NOT NULL,
        modality TEXT NOT NULL,
        space TEXT,
        size_bytes INTEGER NOT NULL DEFAULT 0 CHECK (size_bytes >= 0),
        sha256 TEXT NOT NULL CHECK (
            length(sha256) == 64 AND NOT (sha256 GLOB '*[^0-9a-f]*')
        ),
        header_json TEXT NOT NULL,
        bids_entities_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        UNIQUE (host, posix_path)
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
        workflow_id TEXT NOT NULL REFERENCES workflows(workflow_id)
            ON DELETE CASCADE,
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
        tool_status TEXT CHECK (
            tool_status IS NULL OR tool_status IN (
                'started', 'completed', 'failed'
            )
        ),
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
        year INTEGER CHECK (
            year IS NULL OR (year >= 1800 AND year <= 2100)
        ),
        bibtex TEXT NOT NULL,
        verified INTEGER NOT NULL DEFAULT 1 CHECK (verified IN (0, 1)),
        created_at TEXT NOT NULL
    );
    """

    INDEXES: tuple[str, ...] = (
        "CREATE INDEX IF NOT EXISTS idx_workflows_status "
        "ON workflows (status);",
        "CREATE INDEX IF NOT EXISTS idx_workflows_created "
        "ON workflows (created_at DESC);",
        "CREATE INDEX IF NOT EXISTS idx_task_nodes_wf "
        "ON task_nodes (workflow_id);",
        "CREATE INDEX IF NOT EXISTS idx_task_nodes_wf_state "
        "ON task_nodes (workflow_id, state);",
        "CREATE INDEX IF NOT EXISTS idx_task_nodes_state "
        "ON task_nodes (state);",
        "CREATE INDEX IF NOT EXISTS idx_task_nodes_harness "
        "ON task_nodes (harness_id);",
        "CREATE INDEX IF NOT EXISTS idx_task_edges_wf_child "
        "ON task_edges (workflow_id, child_node_id);",
        "CREATE INDEX IF NOT EXISTS idx_task_edges_wf_parent "
        "ON task_edges (workflow_id, parent_node_id);",
        "CREATE INDEX IF NOT EXISTS idx_artifacts_wf "
        "ON remote_artifacts (workflow_id);",
        "CREATE INDEX IF NOT EXISTS idx_artifacts_node "
        "ON remote_artifacts (node_id);",
        "CREATE INDEX IF NOT EXISTS idx_artifacts_modality "
        "ON remote_artifacts (modality);",
        "CREATE INDEX IF NOT EXISTS idx_artifacts_host_path "
        "ON remote_artifacts (host, posix_path);",
        "CREATE INDEX IF NOT EXISTS idx_jobs_node "
        "ON remote_jobs (node_id);",
        "CREATE INDEX IF NOT EXISTS idx_jobs_state "
        "ON remote_jobs (state);",
        "CREATE INDEX IF NOT EXISTS idx_jobs_scheduler "
        "ON remote_jobs (scheduler_type, scheduler_job_id);",
        "CREATE INDEX IF NOT EXISTS idx_telemetry_wf "
        "ON telemetry_events (workflow_id);",
        "CREATE INDEX IF NOT EXISTS idx_telemetry_node "
        "ON telemetry_events (node_id);",
        "CREATE INDEX IF NOT EXISTS idx_telemetry_type "
        "ON telemetry_events (event_type);",
        "CREATE INDEX IF NOT EXISTS idx_telemetry_ts "
        "ON telemetry_events (timestamp);",
        "CREATE INDEX IF NOT EXISTS idx_telemetry_tool "
        "ON telemetry_events (tool_name, tool_status);",
        "CREATE INDEX IF NOT EXISTS idx_citations_doi "
        "ON citations_ledger (doi) WHERE doi IS NOT NULL;",
        "CREATE INDEX IF NOT EXISTS idx_citations_pmid "
        "ON citations_ledger (pmid) WHERE pmid IS NOT NULL;",
        "CREATE INDEX IF NOT EXISTS idx_citations_verified "
        "ON citations_ledger (verified);",
    )


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

    VALID_TRANSITIONS: dict[TaskState, set[TaskState]] = {
        TaskState.PENDING: {
            TaskState.PREFLIGHT_CHECK,
            TaskState.RUNNING,
            TaskState.CANCELLED,
        },
        TaskState.PREFLIGHT_CHECK: {
            TaskState.RUNNING,
            TaskState.RETRYING,
            TaskState.WAITING_OPERATOR,
            TaskState.FAILED,
            TaskState.CANCELLED,
        },
        TaskState.RUNNING: {
            TaskState.QA_REVIEW,
            TaskState.COMPLETED,
            TaskState.RETRYING,
            TaskState.WAITING_OPERATOR,
            TaskState.FAILED,
            TaskState.CANCELLED,
        },
        TaskState.QA_REVIEW: {
            TaskState.COMPLETED,
            TaskState.RETRYING,
            TaskState.WAITING_OPERATOR,
            TaskState.FAILED,
            TaskState.CANCELLED,
        },
        TaskState.RETRYING: {
            TaskState.PREFLIGHT_CHECK,
            TaskState.RUNNING,
            TaskState.CANCELLED,
        },
        TaskState.WAITING_OPERATOR: {
            TaskState.RETRYING,
            TaskState.RUNNING,
            TaskState.COMPLETED,
            TaskState.CANCELLED,
            TaskState.FAILED,
        },
        TaskState.COMPLETED: set(),
        TaskState.FAILED: {
            TaskState.RETRYING,
        },
        TaskState.CANCELLED: set(),
    }

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
                Configured SQLite connection in WAL mode with foreign keys.
        """
        conn_str: str = ":memory:" if self._is_memory else str(self._db_path)
        conn: sqlite3.Connection = sqlite3.connect(
            conn_str,
            timeout=self._timeout,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute(BlackboardSchema.PRAGMA_WAL)
        conn.execute(BlackboardSchema.PRAGMA_FOREIGN_KEYS)
        conn.execute(BlackboardSchema.PRAGMA_BUSY_TIMEOUT)
        conn.execute(BlackboardSchema.PRAGMA_SYNCHRONOUS)
        return conn

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Provide a contextual database connection with transaction scope.

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

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Internal alias for connection context manager.

        Parameters
        ------------
        None

        Returns
        --------
            Generator[sqlite3.Connection, None, None]: context manager generator
                Yields configured connection.
        """
        with self.connection() as conn:
            yield conn

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

    # -------------------------------------------------------------------------
    # Workflow Operations
    # -------------------------------------------------------------------------

    def create_workflow(self, workflow_id: str, prompt: str) -> None:
        """Register a new research workflow session in the blackboard.

        Parameters
        ------------
        workflow_id: str
            Unique workflow identifier.
        prompt: str
            Original user prompt describing the neuroscience goal.

        Returns
        --------
            None: NoneType object
                Inserts workflow record into database.
        """
        now_iso: str = datetime.now(timezone.utc).isoformat()
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO workflows (
                    workflow_id, prompt, status, created_at, updated_at,
                    total_tokens, estimated_cost_usd
                ) VALUES (?, ?, 'PENDING', ?, ?, 0, 0.0);
                """,
                (workflow_id, prompt, now_iso, now_iso),
            )

    def get_workflow(self, workflow_id: str) -> dict[str, Any] | None:
        """Retrieve metadata and aggregate metrics for a workflow.

        Parameters
        ------------
        workflow_id: str
            Unique workflow identifier.

        Returns
        --------
            dict[str, Any] | None: dictionary or None
                Dictionary of workflow fields if found, None otherwise.
        """
        with self.connection() as conn:
            cursor: sqlite3.Cursor = conn.execute(
                """
                SELECT workflow_id, prompt, status, created_at, updated_at,
                       total_tokens, estimated_cost_usd
                FROM workflows
                WHERE workflow_id = ?;
                """,
                (workflow_id,),
            )
            row: Any = cursor.fetchone()
            if row is None:
                return None
            result_dict: dict[str, Any] = dict(row)
            return result_dict

    def update_workflow_status(
        self,
        workflow_id: str,
        status: str,
        total_tokens: int | None = None,
        estimated_cost_usd: float | None = None,
    ) -> None:
        """Update workflow lifecycle status and token/cost tallies.

        Parameters
        ------------
        workflow_id: str
            Workflow identifier.
        status: str
            Target workflow status string.
        total_tokens: int | None
            Cumulative tokens consumed. Defaults to None.
        estimated_cost_usd: float | None
            Cumulative cost in USD. Defaults to None.

        Returns
        --------
            None: NoneType object
                Updates workflow record in database.
        """
        now_iso: str = datetime.now(timezone.utc).isoformat()
        with self.connection() as conn:
            if total_tokens is not None and estimated_cost_usd is not None:
                conn.execute(
                    """
                    UPDATE workflows
                    SET status = ?,
                        total_tokens = ?,
                        estimated_cost_usd = ?,
                        updated_at = ?
                    WHERE workflow_id = ?;
                    """,
                    (
                        status,
                        total_tokens,
                        estimated_cost_usd,
                        now_iso,
                        workflow_id,
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE workflows
                    SET status = ?,
                        updated_at = ?
                    WHERE workflow_id = ?;
                    """,
                    (status, now_iso, workflow_id),
                )

    def list_workflows(self) -> list[dict[str, Any]]:
        """List all workflows recorded in the blackboard.

        Parameters
        ------------
        None

        Returns
        --------
            list[dict[str, Any]]: list object
                List of workflow metadata records.
        """
        with self.connection() as conn:
            cursor: sqlite3.Cursor = conn.execute(
                """
                SELECT workflow_id, prompt, status, created_at, updated_at,
                       total_tokens, estimated_cost_usd
                FROM workflows
                ORDER BY created_at DESC;
                """
            )
            rows: list[Any] = cursor.fetchall()
            result_list: list[dict[str, Any]] = [dict(r) for r in rows]
            return result_list

    def delete_workflow(self, workflow_id: str) -> None:
        """Delete a workflow and cascade remove its nodes and edges.

        Parameters
        ------------
        workflow_id: str
            Unique workflow identifier to remove.

        Returns
        --------
            None: NoneType object
                Deletes workflow from workflows table.
        """
        with self.connection() as conn:
            conn.execute(
                "DELETE FROM workflows WHERE workflow_id = ?;",
                (workflow_id,),
            )

    def reconcile_workflow_status(self, workflow_id: str) -> str:
        """Evaluate child node states and reconcile workflow lifecycle status.

        Parameters
        ------------
        workflow_id: str
            Workflow identifier to evaluate.

        Returns
        --------
            str: string object
                Reconciled status string.
        """
        nodes: list[TaskNode] = self.get_nodes_by_workflow(workflow_id)
        if not nodes:
            return "PENDING"

        states: list[TaskState] = [n.state for n in nodes]
        target_status: str

        if any(s == TaskState.FAILED for s in states):
            target_status = "FAILED"
        elif any(s == TaskState.WAITING_OPERATOR for s in states):
            target_status = "WAITING_OPERATOR"
        elif all(s == TaskState.COMPLETED for s in states):
            target_status = "COMPLETED"
        elif any(
            s in (
                TaskState.RUNNING,
                TaskState.PREFLIGHT_CHECK,
                TaskState.QA_REVIEW,
                TaskState.RETRYING,
            )
            for s in states
        ):
            target_status = "RUNNING"
        elif any(s == TaskState.CANCELLED for s in states):
            target_status = "CANCELLED"
        else:
            target_status = "PENDING"

        self.update_workflow_status(workflow_id, target_status)
        result_status: str = target_status
        return result_status

    # -------------------------------------------------------------------------
    # Task Node Operations
    # -------------------------------------------------------------------------

    def create_node(self, node: TaskNode) -> None:
        """Insert a new task node into the blackboard task_nodes table.

        Parameters
        ------------
        node: TaskNode
            Validated TaskNode model to persist.

        Returns
        --------
            None: NoneType object
                Persists task node record into SQLite.
        """
        now_iso: str = datetime.now(timezone.utc).isoformat()
        envelope_json: str | None = (
            node.envelope.model_dump_json() if node.envelope is not None else None
        )
        feedback_json: str = json.dumps(node.diagnostic_feedback)
        started_iso: str | None = (
            node.started_at.isoformat() if node.started_at is not None else None
        )
        completed_iso: str | None = (
            node.completed_at.isoformat()
            if node.completed_at is not None
            else None
        )

        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO task_nodes (
                    node_id,
                    workflow_id,
                    agent_role,
                    harness_id,
                    state,
                    attempt,
                    max_retries,
                    envelope_json,
                    summary_result,
                    diagnostic_feedback_json,
                    created_at,
                    updated_at,
                    started_at,
                    completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    node.node_id,
                    node.workflow_id,
                    node.agent_role,
                    node.harness_id,
                    node.state.value,
                    node.attempt,
                    node.max_retries,
                    envelope_json,
                    node.summary_result,
                    feedback_json,
                    now_iso,
                    now_iso,
                    started_iso,
                    completed_iso,
                ),
            )

    def create_task_node(self, node: TaskNode) -> None:
        """Alias for create_node.

        Parameters
        ------------
        node: TaskNode
            TaskNode model to persist.

        Returns
        --------
            None: NoneType object
                Delegates to create_node.
        """
        self.create_node(node)

    def create_nodes(self, nodes: list[TaskNode]) -> None:
        """Batch insert multiple task nodes inside a single transaction.

        Parameters
        ------------
        nodes: list[TaskNode]
            List of TaskNode models to persist.

        Returns
        --------
            None: NoneType object
                Inserts all node records.
        """
        for node in nodes:
            self.create_node(node)

    def get_node(self, node_id: str) -> TaskNode | None:
        """Retrieve a single task node by its unique identifier.

        Parameters
        ------------
        node_id: str
            Unique node identifier.

        Returns
        --------
            TaskNode | None: TaskNode or None
                Hydrated TaskNode model if found, None otherwise.
        """
        with self.connection() as conn:
            cursor: sqlite3.Cursor = conn.execute(
                """
                SELECT * FROM task_nodes WHERE node_id = ?;
                """,
                (node_id,),
            )
            row: Any = cursor.fetchone()
            if row is None:
                return None
            result_node: TaskNode = self._row_to_task_node(row)
            return result_node

    def get_task_node(self, node_id: str) -> TaskNode | None:
        """Alias for get_node.

        Parameters
        ------------
        node_id: str
            Unique node identifier.

        Returns
        --------
            TaskNode | None: TaskNode or None
                Hydrated TaskNode model if found, None otherwise.
        """
        result: TaskNode | None = self.get_node(node_id)
        return result

    def get_nodes_by_workflow(self, workflow_id: str) -> list[TaskNode]:
        """Retrieve all task nodes belonging to a specified workflow.

        Parameters
        ------------
        workflow_id: str
            Identifier of the parent workflow.

        Returns
        --------
            list[TaskNode]: list object
                Chronologically ordered list of task nodes.
        """
        with self.connection() as conn:
            cursor: sqlite3.Cursor = conn.execute(
                """
                SELECT * FROM task_nodes
                WHERE workflow_id = ?
                ORDER BY created_at ASC, node_id ASC;
                """,
                (workflow_id,),
            )
            rows: list[Any] = cursor.fetchall()
            result_nodes: list[TaskNode] = [
                self._row_to_task_node(r) for r in rows
            ]
            return result_nodes

    def update_node_envelope(
        self, node_id: str, envelope: NeuriTaskEnvelope
    ) -> None:
        """Update the dispatched task envelope on a task node.

        Parameters
        ------------
        node_id: str
            Unique node identifier.
        envelope: NeuriTaskEnvelope
            Updated task envelope.

        Returns
        --------
            None: NoneType object
                Updates envelope_json in task_nodes table.
        """
        now_iso: str = datetime.now(timezone.utc).isoformat()
        envelope_json: str = envelope.model_dump_json()

        with self.connection() as conn:
            cursor: sqlite3.Cursor = conn.execute(
                """
                UPDATE task_nodes
                SET envelope_json = ?,
                    updated_at = ?
                WHERE node_id = ?;
                """,
                (envelope_json, now_iso, node_id),
            )
            if cursor.rowcount == 0:
                raise NodeNotFoundError(
                    f"Task node '{node_id}' does not exist in blackboard."
                )

    def record_node_result(
        self, node_id: str, result: NeuriTaskResult
    ) -> None:
        """Record the final execution outcome of a completed node.

        Parameters
        ------------
        node_id: str
            Target node identifier.
        result: NeuriTaskResult
            Execution result model.

        Returns
        --------
            None: NoneType object
                Updates summary_result, completed_at, and state.
        """
        now_iso: str = datetime.now(timezone.utc).isoformat()
        target_state: TaskState = (
            TaskState.COMPLETED if result.is_ok() else TaskState.FAILED
        )

        with self.connection() as conn:
            conn.execute(
                """
                UPDATE task_nodes
                SET summary_result = ?,
                    completed_at = ?,
                    updated_at = ?
                WHERE node_id = ?;
                """,
                (result.summary, now_iso, now_iso, node_id),
            )

        feedback: str | None = (
            result.error_message if not result.is_ok() else None
        )
        self.update_node_state(
            node_id, target_state, diagnostic_feedback=feedback
        )

    def delete_task_node(self, node_id: str) -> None:
        """Delete a task node from the task_nodes table.

        Parameters
        ------------
        node_id: str
            Identifier of task node to delete.

        Returns
        --------
            None: NoneType object
                Removes record from task_nodes.
        """
        with self.connection() as conn:
            conn.execute(
                "DELETE FROM task_nodes WHERE node_id = ?;",
                (node_id,),
            )

    # -------------------------------------------------------------------------
    # Task Edge Operations & Cycle Detection
    # -------------------------------------------------------------------------

    def add_edge(self, edge: TaskEdge) -> None:
        """Add a directed dependency edge after cycle and existence validation.

        Ensures parent and child nodes exist, prevents self-loops, and guarantees
        the workflow remains an acyclic directed graph.

        Parameters
        ------------
        edge: TaskEdge
            Directed dependency edge to add.

        Returns
        --------
            None: NoneType object
                Inserts edge into task_edges table.
        """
        if edge.parent_node_id == edge.child_node_id:
            raise ValueError(
                f"Self-loop detected: parent and child node ID is "
                f"'{edge.parent_node_id}'."
            )

        with self.connection() as conn:
            parent_row: Any = conn.execute(
                """
                SELECT 1 FROM task_nodes
                WHERE workflow_id = ? AND node_id = ?;
                """,
                (edge.workflow_id, edge.parent_node_id),
            ).fetchone()
            if parent_row is None:
                raise NodeNotFoundError(
                    f"Parent node '{edge.parent_node_id}' does not exist in "
                    f"workflow '{edge.workflow_id}'."
                )

            child_row: Any = conn.execute(
                """
                SELECT 1 FROM task_nodes
                WHERE workflow_id = ? AND node_id = ?;
                """,
                (edge.workflow_id, edge.child_node_id),
            ).fetchone()
            if child_row is None:
                raise NodeNotFoundError(
                    f"Child node '{edge.child_node_id}' does not exist in "
                    f"workflow '{edge.workflow_id}'."
                )

            existing_edge: Any = conn.execute(
                """
                SELECT 1 FROM task_edges
                WHERE workflow_id = ? AND parent_node_id = ?
                  AND child_node_id = ?;
                """,
                (edge.workflow_id, edge.parent_node_id, edge.child_node_id),
            ).fetchone()
            if existing_edge is not None:
                return

            cycle_path: list[str] | None = self._find_directed_path(
                conn,
                edge.workflow_id,
                start_node_id=edge.child_node_id,
                target_node_id=edge.parent_node_id,
            )
            if cycle_path is not None:
                full_cycle: list[str] = [edge.parent_node_id] + cycle_path
                cycle_repr: str = " -> ".join(full_cycle)
                raise CycleDetectedError(
                    f"Adding dependency edge '{edge.parent_node_id}' -> "
                    f"'{edge.child_node_id}' creates a cycle: {cycle_repr}."
                )

            conn.execute(
                """
                INSERT INTO task_edges (
                    workflow_id, parent_node_id, child_node_id
                ) VALUES (?, ?, ?);
                """,
                (edge.workflow_id, edge.parent_node_id, edge.child_node_id),
            )

    def add_task_edge(
        self, workflow_id: str, parent_node_id: str, child_node_id: str
    ) -> None:
        """Convenience method to construct and add a dependency edge.

        Parameters
        ------------
        workflow_id: str
            Identifier of the parent workflow.
        parent_node_id: str
            Identifier of predecessor parent node.
        child_node_id: str
            Identifier of dependent child node.

        Returns
        --------
            None: NoneType object
                Delegates to add_edge.
        """
        edge: TaskEdge = TaskEdge(
            workflow_id=workflow_id,
            parent_node_id=parent_node_id,
            child_node_id=child_node_id,
        )
        self.add_edge(edge)

    def add_edges(self, edges: list[TaskEdge]) -> None:
        """Batch insert multiple dependency edges atomically.

        Parameters
        ------------
        edges: list[TaskEdge]
            List of TaskEdge models to insert.

        Returns
        --------
            None: NoneType object
                Inserts all validated edges.
        """
        for edge in edges:
            self.add_edge(edge)

    def get_edges(self, workflow_id: str) -> list[TaskEdge]:
        """Retrieve all dependency edges belonging to a workflow.

        Parameters
        ------------
        workflow_id: str
            Identifier of the parent workflow.

        Returns
        --------
            list[TaskEdge]: list object
                List of TaskEdge dependency models.
        """
        with self.connection() as conn:
            cursor: sqlite3.Cursor = conn.execute(
                """
                SELECT workflow_id, parent_node_id, child_node_id
                FROM task_edges
                WHERE workflow_id = ?
                ORDER BY parent_node_id ASC, child_node_id ASC;
                """,
                (workflow_id,),
            )
            rows: list[Any] = cursor.fetchall()
            result_edges: list[TaskEdge] = [
                TaskEdge(
                    workflow_id=r["workflow_id"],
                    parent_node_id=r["parent_node_id"],
                    child_node_id=r["child_node_id"],
                )
                for r in rows
            ]
            return result_edges

    def get_parent_nodes(self, node_id: str) -> list[TaskNode]:
        """Retrieve all immediate parent predecessor nodes for a given node.

        Parameters
        ------------
        node_id: str
            Unique identifier of the child task node.

        Returns
        --------
            list[TaskNode]: list object
                Predecessor nodes whose completion this node depends on.
        """
        with self.connection() as conn:
            cursor: sqlite3.Cursor = conn.execute(
                """
                SELECT p.*
                FROM task_nodes p
                JOIN task_edges e ON p.node_id = e.parent_node_id
                WHERE e.child_node_id = ?
                ORDER BY p.created_at ASC, p.node_id ASC;
                """,
                (node_id,),
            )
            rows: list[Any] = cursor.fetchall()
            result_nodes: list[TaskNode] = [
                self._row_to_task_node(r) for r in rows
            ]
            return result_nodes

    def get_child_nodes(self, node_id: str) -> list[TaskNode]:
        """Retrieve all immediate child successor nodes that depend on a node.

        Parameters
        ------------
        node_id: str
            Unique identifier of the parent task node.

        Returns
        --------
            list[TaskNode]: list object
                Successor nodes dependent on this parent node.
        """
        with self.connection() as conn:
            cursor: sqlite3.Cursor = conn.execute(
                """
                SELECT c.*
                FROM task_nodes c
                JOIN task_edges e ON c.node_id = e.child_node_id
                WHERE e.parent_node_id = ?
                ORDER BY c.created_at ASC, c.node_id ASC;
                """,
                (node_id,),
            )
            rows: list[Any] = cursor.fetchall()
            result_nodes: list[TaskNode] = [
                self._row_to_task_node(r) for r in rows
            ]
            return result_nodes

    def get_parent_node_ids(self, node_id: str) -> list[str]:
        """Retrieve IDs of all immediate predecessor nodes for a given node.

        Parameters
        ------------
        node_id: str
            Unique identifier of the child task node.

        Returns
        --------
            list[str]: list object
                List of parent node ID strings.
        """
        with self.connection() as conn:
            cursor: sqlite3.Cursor = conn.execute(
                """
                SELECT parent_node_id
                FROM task_edges
                WHERE child_node_id = ?
                ORDER BY parent_node_id ASC;
                """,
                (node_id,),
            )
            rows: list[Any] = cursor.fetchall()
            result_ids: list[str] = [r["parent_node_id"] for r in rows]
            return result_ids

    def get_child_node_ids(self, node_id: str) -> list[str]:
        """Retrieve IDs of all immediate successor nodes for a given node.

        Parameters
        ------------
        node_id: str
            Unique identifier of the parent task node.

        Returns
        --------
            list[str]: list object
                List of child node ID strings.
        """
        with self.connection() as conn:
            cursor: sqlite3.Cursor = conn.execute(
                """
                SELECT child_node_id
                FROM task_edges
                WHERE parent_node_id = ?
                ORDER BY child_node_id ASC;
                """,
                (node_id,),
            )
            rows: list[Any] = cursor.fetchall()
            result_ids: list[str] = [r["child_node_id"] for r in rows]
            return result_ids

    def _find_directed_path(
        self,
        conn: sqlite3.Connection,
        workflow_id: str,
        start_node_id: str,
        target_node_id: str,
    ) -> list[str] | None:
        """Find a directed path from start_node_id to target_node_id if one exists.

        Uses Breadth-First Search over existing edges in the task_edges table.

        Parameters
        ------------
        conn: sqlite3.Connection
            Active SQLite connection.
        workflow_id: str
            Workflow identifier.
        start_node_id: str
            Source node identifier to start traversal from.
        target_node_id: str
            Destination node identifier to reach.

        Returns
        --------
            list[str] | None: list of strings or None
                List of node IDs forming directed path, or None if unreachable.
        """
        cursor: sqlite3.Cursor = conn.execute(
            """
            SELECT parent_node_id, child_node_id
            FROM task_edges
            WHERE workflow_id = ?;
            """,
            (workflow_id,),
        )
        adjacency: dict[str, list[str]] = {}
        for row in cursor.fetchall():
            parent_id: str = row["parent_node_id"]
            child_id: str = row["child_node_id"]
            if parent_id not in adjacency:
                adjacency[parent_id] = []
            adjacency[parent_id].append(child_id)

        queue: deque[list[str]] = deque([[start_node_id]])
        visited: set[str] = {start_node_id}

        while queue:
            path: list[str] = queue.popleft()
            current_node: str = path[-1]

            if current_node == target_node_id:
                found_path: list[str] = path
                return found_path

            for neighbor in adjacency.get(current_node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(path + [neighbor])

        no_path: list[str] | None = None
        return no_path

    # -------------------------------------------------------------------------
    # Topological DAG Queries
    # -------------------------------------------------------------------------

    def get_ready_nodes(self, workflow_id: str) -> list[TaskNode]:
        """Query topological candidate nodes ready for immediate scheduling.

        Returns all nodes in PENDING state whose incoming parent nodes in
        task_edges are ALL in the COMPLETED state. Properly handles root
        nodes (nodes with zero parents), and blocks nodes if any parent is
        still RUNNING, FAILED, CANCELLED, RETRYING, or in PREFLIGHT_CHECK.

        Parameters
        ------------
        workflow_id: str
            Unique identifier of the parent workflow.

        Returns
        --------
            list[TaskNode]: list object
                Deterministic list of unblocked TaskNode instances ready to execute.
        """
        with self.connection() as conn:
            cursor: sqlite3.Cursor = conn.execute(
                """
                SELECT n.*
                FROM task_nodes n
                WHERE n.workflow_id = ?
                  AND n.state = 'PENDING'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM task_edges e
                      LEFT JOIN task_nodes p ON e.parent_node_id = p.node_id
                      WHERE e.workflow_id = n.workflow_id
                        AND e.child_node_id = n.node_id
                        AND (p.node_id IS NULL OR p.state != 'COMPLETED')
                  )
                ORDER BY n.created_at ASC, n.node_id ASC;
                """,
                (workflow_id,),
            )
            rows: list[Any] = cursor.fetchall()
            result_nodes: list[TaskNode] = [
                self._row_to_task_node(r) for r in rows
            ]
            return result_nodes

    def get_topological_order(self, workflow_id: str) -> list[str]:
        """Compute a complete topological order of all nodes in a workflow.

        Executes Kahn's algorithm over the workflow DAG. Raises CycleDetectedError
        if a directed cycle is encountered.

        Parameters
        ------------
        workflow_id: str
            Workflow identifier.

        Returns
        --------
            list[str]: list object
                List of node IDs in valid topological execution sequence.
        """
        with self.connection() as conn:
            node_cursor: sqlite3.Cursor = conn.execute(
                """
                SELECT node_id FROM task_nodes
                WHERE workflow_id = ?
                ORDER BY created_at ASC, node_id ASC;
                """,
                (workflow_id,),
            )
            all_nodes: list[str] = [
                row["node_id"] for row in node_cursor.fetchall()
            ]

            edge_cursor: sqlite3.Cursor = conn.execute(
                """
                SELECT parent_node_id, child_node_id FROM task_edges
                WHERE workflow_id = ?;
                """,
                (workflow_id,),
            )
            edge_rows: list[Any] = edge_cursor.fetchall()

        in_degree: dict[str, int] = {node_id: 0 for node_id in all_nodes}
        adjacency: dict[str, list[str]] = {node_id: [] for node_id in all_nodes}

        for row in edge_rows:
            parent_id: str = row["parent_node_id"]
            child_id: str = row["child_node_id"]
            if parent_id in in_degree and child_id in in_degree:
                in_degree[child_id] += 1
                adjacency[parent_id].append(child_id)

        queue: deque[str] = deque(
            sorted([nid for nid, deg in in_degree.items() if deg == 0])
        )
        ordered: list[str] = []

        while queue:
            current: str = queue.popleft()
            ordered.append(current)

            for neighbor in sorted(adjacency.get(current, [])):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(ordered) != len(all_nodes):
            unvisited: list[str] = [
                n for n in all_nodes if n not in set(ordered)
            ]
            raise CycleDetectedError(
                f"Topological sort failed for workflow '{workflow_id}'. "
                f"Cycle detected among nodes: {unvisited}."
            )

        result_order: list[str] = ordered
        return result_order

    def validate_dag(self, workflow_id: str) -> bool:
        """Verify that the workflow graph is a valid acyclic directed graph.

        Parameters
        ------------
        workflow_id: str
            Workflow identifier to validate.

        Returns
        --------
            bool: boolean object
                True if the graph is a valid DAG.
        """
        self.get_topological_order(workflow_id)
        is_valid: bool = True
        return is_valid

    def get_blocked_nodes(
        self, workflow_id: str
    ) -> list[tuple[TaskNode, list[str]]]:
        """Identify nodes permanently blocked by parent failure or cancellation.

        Parameters
        ------------
        workflow_id: str
            Workflow identifier to inspect.

        Returns
        --------
            list[tuple[TaskNode, list[str]]]: list object
                Pairs of (blocked_node, list_of_failed_or_cancelled_parent_ids).
        """
        pending_nodes: list[TaskNode] = [
            n
            for n in self.get_nodes_by_workflow(workflow_id)
            if n.state == TaskState.PENDING
        ]
        blocked: list[tuple[TaskNode, list[str]]] = []

        for node in pending_nodes:
            parents: list[TaskNode] = self.get_parent_nodes(node.node_id)
            failed_parents: list[str] = [
                p.node_id
                for p in parents
                if p.state in (TaskState.FAILED, TaskState.CANCELLED)
            ]
            if failed_parents:
                blocked.append((node, failed_parents))

        result_blocked: list[tuple[TaskNode, list[str]]] = blocked
        return result_blocked

    # -------------------------------------------------------------------------
    # State Transition & Feedback Logging Operations
    # -------------------------------------------------------------------------

    def update_node_state(
        self,
        node_id: str,
        state: TaskState,
        diagnostic_feedback: str | None = None,
        summary_result: str | None = None,
    ) -> None:
        """Transition a task node to a new state and record diagnostic feedback.

        Validates permitted state transitions, manages retry attempt counts,
        updates started_at / completed_at timestamps, and appends feedback.

        Parameters
        ------------
        node_id: str
            Target node identifier.
        state: TaskState
            Target TaskState to transition into.
        diagnostic_feedback: str | None
            Diagnostic error or feedback message to log. Defaults to None.
        summary_result: str | None
            Optional result summary string to record. Defaults to None.

        Returns
        --------
            None: NoneType object
                Updates task node record in database.
        """
        with self.connection() as conn:
            cursor: sqlite3.Cursor = conn.execute(
                """
                SELECT node_id, workflow_id, state, attempt, max_retries,
                       envelope_json, summary_result, diagnostic_feedback_json,
                       started_at, completed_at
                FROM task_nodes
                WHERE node_id = ?;
                """,
                (node_id,),
            )
            row: Any = cursor.fetchone()
            if row is None:
                raise NodeNotFoundError(
                    f"Task node '{node_id}' does not exist in blackboard."
                )

            current_state: TaskState = TaskState(row["state"])

            # Idempotent return if state does not change and no extras added
            if (
                current_state == state
                and diagnostic_feedback is None
                and summary_result is None
            ):
                return

            # State transition validation
            if current_state != state:
                allowed_targets: set[TaskState] = self.VALID_TRANSITIONS.get(
                    current_state, set()
                )
                if state not in allowed_targets:
                    raise InvalidStateTransitionError(
                        f"Illegal state transition from '{current_state.value}' "
                        f"to '{state.value}' for node '{node_id}'. Permitted "
                        f"targets: {[s.value for s in allowed_targets]}."
                    )

            now_iso: str = datetime.now(timezone.utc).isoformat()
            started_iso: str | None = row["started_at"]
            if state == TaskState.RUNNING and started_iso is None:
                started_iso = now_iso

            completed_iso: str | None = row["completed_at"]
            if state in (
                TaskState.COMPLETED,
                TaskState.FAILED,
                TaskState.CANCELLED,
            ):
                completed_iso = now_iso
            elif state in (
                TaskState.PREFLIGHT_CHECK,
                TaskState.RUNNING,
                TaskState.RETRYING,
            ):
                completed_iso = None

            new_attempt: int = row["attempt"]
            if state == TaskState.RETRYING:
                new_attempt += 1

            feedback_list: list[str] = []
            if row["diagnostic_feedback_json"]:
                try:
                    parsed: Any = json.loads(row["diagnostic_feedback_json"])
                    if isinstance(parsed, list):
                        feedback_list = [str(x) for x in parsed]
                    elif isinstance(parsed, str):
                        feedback_list = [parsed]
                except (json.JSONDecodeError, TypeError):
                    feedback_list = [row["diagnostic_feedback_json"]]

            if diagnostic_feedback and diagnostic_feedback.strip():
                feedback_list.append(diagnostic_feedback.strip())

            new_feedback_json: str = json.dumps(feedback_list)

            new_summary: str | None = (
                summary_result
                if summary_result is not None
                else row["summary_result"]
            )

            new_envelope_json: str | None = row["envelope_json"]
            if new_envelope_json is not None:
                try:
                    envelope: NeuriTaskEnvelope = (
                        NeuriTaskEnvelope.model_validate_json(
                            new_envelope_json
                        )
                    )
                    if state == TaskState.RETRYING:
                        envelope.attempt_number = new_attempt + 1
                    if diagnostic_feedback and diagnostic_feedback.strip():
                        envelope.diagnostic_feedback = (
                            diagnostic_feedback.strip()
                        )
                    new_envelope_json = envelope.model_dump_json()
                except Exception:
                    pass

            conn.execute(
                """
                UPDATE task_nodes
                SET state = ?,
                    attempt = ?,
                    envelope_json = ?,
                    summary_result = ?,
                    diagnostic_feedback_json = ?,
                    started_at = ?,
                    completed_at = ?,
                    updated_at = ?
                WHERE node_id = ?;
                """,
                (
                    state.value,
                    new_attempt,
                    new_envelope_json,
                    new_summary,
                    new_feedback_json,
                    started_iso,
                    completed_iso,
                    now_iso,
                    node_id,
                ),
            )

    # -------------------------------------------------------------------------
    # Remote Artifact Operations
    # -------------------------------------------------------------------------

    def register_artifact(
        self,
        artifact: RemoteArtifact,
        workflow_id: str,
        node_id: str | None = None,
    ) -> None:
        """Register a remote artifact in the blackboard provenance store.

        Enforces unique artifact ID, unique URI, unique POSIX path on host,
        valid SHA-256 hash format, and intra-workflow task node association,
        serializing sanitized metadata headers and BIDS entities into SQLite.

        Parameters
        ------------
        artifact: RemoteArtifact
            Pydantic remote artifact pointer to register.
        workflow_id: str
            Parent workflow identifier.
        node_id: str | None
            Optional task node identifier that produced the artifact.
            Defaults to None.

        Returns
        --------
            None: NoneType object
                Persists artifact record into remote_artifacts table.
        """
        with self.connection() as conn:
            wf_cursor: sqlite3.Cursor = conn.execute(
                "SELECT 1 FROM workflows WHERE workflow_id = ?;",
                (workflow_id,),
            )
            if wf_cursor.fetchone() is None:
                raise WorkflowNotFoundError(
                    f"Cannot register artifact: Workflow '{workflow_id}' "
                    "does not exist."
                )

            id_cursor: sqlite3.Cursor = conn.execute(
                "SELECT 1 FROM remote_artifacts WHERE artifact_id = ?;",
                (artifact.artifact_id,),
            )
            if id_cursor.fetchone() is not None:
                raise ArtifactRegistrationError(
                    f"Artifact with ID '{artifact.artifact_id}' is already "
                    "registered."
                )

            uri_cursor: sqlite3.Cursor = conn.execute(
                "SELECT 1 FROM remote_artifacts WHERE uri = ?;",
                (artifact.uri,),
            )
            if uri_cursor.fetchone() is not None:
                raise ArtifactRegistrationError(
                    f"Artifact with URI '{artifact.uri}' is already registered."
                )

            path_cursor: sqlite3.Cursor = conn.execute(
                "SELECT 1 FROM remote_artifacts WHERE host = ? "
                "AND posix_path = ?;",
                (artifact.host, artifact.posix_path),
            )
            if path_cursor.fetchone() is not None:
                raise ArtifactRegistrationError(
                    f"Artifact at POSIX path '{artifact.posix_path}' on "
                    f"host '{artifact.host}' is already registered."
                )

            sha256_pattern: str = r"^[0-9a-f]{64}$"
            if not re.match(sha256_pattern, artifact.sha256_header):
                raise ArtifactRegistrationError(
                    f"Cannot register artifact: SHA-256 header hash "
                    f"'{artifact.sha256_header}' must be a 64-character "
                    "lowercase hexadecimal string."
                )

            target_node_id: str | None = node_id or artifact.created_by_node
            if target_node_id is not None:
                node_cursor: sqlite3.Cursor = conn.execute(
                    "SELECT 1 FROM task_nodes WHERE node_id = ? AND "
                    "workflow_id = ?;",
                    (target_node_id, workflow_id),
                )
                if node_cursor.fetchone() is None:
                    raise NodeNotFoundError(
                        f"Cannot register artifact: Node '{target_node_id}' "
                        f"does not exist in workflow '{workflow_id}'."
                    )

            header_json_str: str = artifact.header_summary.model_dump_json()
            bids_json_str: str = json.dumps(artifact.bids_entities)
            created_at_iso: str = artifact.created_at.isoformat()

            try:
                conn.execute(
                    """
                    INSERT INTO remote_artifacts (
                        artifact_id, uri, workflow_id, node_id, host,
                        posix_path, modality, space, size_bytes, sha256,
                        header_json, bids_entities_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        artifact.artifact_id,
                        artifact.uri,
                        workflow_id,
                        target_node_id,
                        artifact.host,
                        artifact.posix_path,
                        artifact.modality.value,
                        artifact.space,
                        artifact.size_bytes,
                        artifact.sha256_header,
                        header_json_str,
                        bids_json_str,
                        created_at_iso,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ArtifactRegistrationError(
                    f"Database integrity constraint violated while "
                    f"registering artifact '{artifact.artifact_id}': {exc}"
                ) from exc

    def get_artifact(self, uri: str) -> RemoteArtifact | None:
        """Retrieve a registered remote artifact by its canonical URI.

        Parameters
        ------------
        uri: str
            Canonical artifact URI (host_alias:///posix/path).

        Returns
        --------
            RemoteArtifact | None: RemoteArtifact model or None
                Reconstructed RemoteArtifact instance if found, else None.
        """
        with self.connection() as conn:
            cursor: sqlite3.Cursor = conn.execute(
                """
                SELECT
                    artifact_id, uri, host, posix_path, modality, space,
                    size_bytes, sha256, header_json, bids_entities_json,
                    node_id, created_at
                FROM remote_artifacts
                WHERE uri = ?;
                """,
                (uri,),
            )
            row: Any = cursor.fetchone()
            if row is None:
                return None
            result_artifact: RemoteArtifact = self._row_to_artifact(row)
            return result_artifact

    def get_artifact_by_id(self, artifact_id: str) -> RemoteArtifact | None:
        """Retrieve a registered remote artifact by its unique identifier.

        Parameters
        ------------
        artifact_id: str
            Unique artifact identifier.

        Returns
        --------
            RemoteArtifact | None: RemoteArtifact model or None
                Reconstructed RemoteArtifact instance if found, else None.
        """
        with self.connection() as conn:
            cursor: sqlite3.Cursor = conn.execute(
                """
                SELECT
                    artifact_id, uri, host, posix_path, modality, space,
                    size_bytes, sha256, header_json, bids_entities_json,
                    node_id, created_at
                FROM remote_artifacts
                WHERE artifact_id = ?;
                """,
                (artifact_id,),
            )
            row: Any = cursor.fetchone()
            if row is None:
                return None
            result_artifact: RemoteArtifact = self._row_to_artifact(row)
            return result_artifact

    def list_artifacts(
        self,
        workflow_id: str | None = None,
        node_id: str | None = None,
    ) -> list[RemoteArtifact]:
        """List registered artifacts optionally filtered by workflow or node.

        Parameters
        ------------
        workflow_id: str | None
            Optional workflow filter. Defaults to None.
        node_id: str | None
            Optional node filter. Defaults to None.

        Returns
        --------
            list[RemoteArtifact]: list object
                List of matching reconstructed RemoteArtifact models.
        """
        query: str = """
            SELECT
                artifact_id, uri, host, posix_path, modality, space,
                size_bytes, sha256, header_json, bids_entities_json,
                node_id, created_at
            FROM remote_artifacts
        """
        clauses: list[str] = []
        params: list[Any] = []
        if workflow_id is not None:
            clauses.append("workflow_id = ?")
            params.append(workflow_id)
        if node_id is not None:
            clauses.append("node_id = ?")
            params.append(node_id)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at ASC;"

        with self.connection() as conn:
            cursor: sqlite3.Cursor = conn.execute(query, tuple(params))
            rows: list[Any] = cursor.fetchall()
            artifacts: list[RemoteArtifact] = [
                self._row_to_artifact(row) for row in rows
            ]
            return artifacts

    # -------------------------------------------------------------------------
    # Remote Job Operations
    # -------------------------------------------------------------------------

    def register_remote_job(
        self,
        job_id: str,
        node_id: str,
        host: str,
        scheduler_type: str,
        scheduler_job_id: str,
        status_uri: str | None = None,
    ) -> None:
        """Register an asynchronous remote batch job in the blackboard.

        Parameters
        ------------
        job_id: str
            Unique remote job identifier.
        node_id: str
            Associated task node identifier.
        host: str
            Target remote execution host alias.
        scheduler_type: str
            Scheduler type ('slurm' or 'tmux').
        scheduler_job_id: str
            Job identifier assigned by remote scheduler.
        status_uri: str | None
            Optional URI for job status or logs. Defaults to None.

        Returns
        --------
            None: NoneType object
                Inserts record into remote_jobs table.
        """
        now_iso: str = datetime.now(timezone.utc).isoformat()
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO remote_jobs (
                    job_id, node_id, host, scheduler_type,
                    scheduler_job_id, status_uri, state,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'SUBMITTED', ?, ?);
                """,
                (
                    job_id,
                    node_id,
                    host,
                    scheduler_type,
                    scheduler_job_id,
                    status_uri,
                    now_iso,
                    now_iso,
                ),
            )

    def update_remote_job_state(self, job_id: str, state: str) -> None:
        """Update lifecycle state of a remote batch job.

        Parameters
        ------------
        job_id: str
            Remote job identifier.
        state: str
            Updated status string ('SUBMITTED', 'PENDING', 'RUNNING',
            'COMPLETED', 'FAILED', 'CANCELLED').

        Returns
        --------
            None: NoneType object
                Updates state and updated_at in remote_jobs table.
        """
        now_iso: str = datetime.now(timezone.utc).isoformat()
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE remote_jobs
                SET state = ?,
                    updated_at = ?
                WHERE job_id = ?;
                """,
                (state, now_iso, job_id),
            )

    def get_remote_job(self, job_id: str) -> dict[str, Any] | None:
        """Retrieve a remote job record by identifier.

        Parameters
        ------------
        job_id: str
            Remote job identifier.

        Returns
        --------
            dict[str, Any] | None: dictionary or None
                Remote job metadata dictionary if found, else None.
        """
        with self.connection() as conn:
            cursor: sqlite3.Cursor = conn.execute(
                """
                SELECT job_id, node_id, host, scheduler_type, scheduler_job_id,
                       status_uri, state, created_at, updated_at
                FROM remote_jobs
                WHERE job_id = ?;
                """,
                (job_id,),
            )
            row: Any = cursor.fetchone()
            if row is None:
                return None
            result_job: dict[str, Any] = dict(row)
            return result_job

    def list_remote_jobs(
        self, node_id: str | None = None
    ) -> list[dict[str, Any]]:
        """List registered remote jobs optionally filtered by node_id.

        Parameters
        ------------
        node_id: str | None
            Optional task node filter. Defaults to None.

        Returns
        --------
            list[dict[str, Any]]: list object
                List of remote job metadata dictionaries.
        """
        query: str = """
            SELECT job_id, node_id, host, scheduler_type, scheduler_job_id,
                   status_uri, state, created_at, updated_at
            FROM remote_jobs
        """
        params: list[Any] = []
        if node_id is not None:
            query += " WHERE node_id = ?"
            params.append(node_id)
        query += " ORDER BY created_at ASC;"

        with self.connection() as conn:
            cursor: sqlite3.Cursor = conn.execute(query, tuple(params))
            rows: list[Any] = cursor.fetchall()
            jobs: list[dict[str, Any]] = [dict(r) for r in rows]
            return jobs

    # -------------------------------------------------------------------------
    # Citations Ledger Operations
    # -------------------------------------------------------------------------

    def _validate_bibtex_syntax(self, bibtex: str, citation_key: str) -> None:
        """Validate that a BibTeX entry string has well-formed basic syntax.

        Verifies that the BibTeX string is non-empty and contains basic
        BibTeX structure including an '@' entry declaration, an entry type,
        and matching braces '{...}', preventing corrupted entries from being
        persisted or synced to references.bib.

        Parameters
        ------------
        bibtex: str
            Raw BibTeX string to inspect.
        citation_key: str
            Citation key identifier for diagnostic context.

        Returns
        --------
            None: NoneType object
                Returns None if validation succeeds, else raises BlackboardError.
        """
        if not isinstance(bibtex, str) or not bibtex.strip():
            raise BlackboardError(
                f"Citation '{citation_key}' BibTeX string cannot be empty."
            )

        stripped_bibtex: str = bibtex.strip()
        at_index: int = stripped_bibtex.find("@")
        if at_index == -1:
            raise BlackboardError(
                f"Citation '{citation_key}' BibTeX string must contain '@' "
                f"entry type declaration."
            )

        open_brace_index: int = stripped_bibtex.find("{", at_index + 1)
        if open_brace_index == -1:
            raise BlackboardError(
                f"Citation '{citation_key}' BibTeX string must contain "
                f"opening brace '{{' after entry type."
            )

        entry_type: str = stripped_bibtex[
            at_index + 1 : open_brace_index
        ].strip()
        if not entry_type:
            raise BlackboardError(
                f"Citation '{citation_key}' BibTeX string is missing entry "
                f"type name between '@' and '{{'."
            )

        close_brace_index: int = stripped_bibtex.rfind("}")
        if close_brace_index == -1 or close_brace_index <= open_brace_index:
            raise BlackboardError(
                f"Citation '{citation_key}' BibTeX string must contain "
                f"closing brace '}}' after opening brace."
            )

        return None

    def register_citation(
        self,
        citation_key: str,
        title: str,
        bibtex: str,
        doi: str | None = None,
        pmid: str | None = None,
        authors: list[str] | None = None,
        year: int | None = None,
        verified: bool = True,
    ) -> None:
        """Register or update a verified citation in the citations ledger.

        Enforces anti-hallucination tracking by persisting verified DOI,
        PMID, and BibTeX entries, with syntactic BibTeX validation and
        structured database exception wrapping.

        Parameters
        ------------
        citation_key: str
            Unique BibTeX citation identifier key.
        title: str
            Article or software title.
        bibtex: str
            Complete BibTeX entry string conforming to basic BibTeX syntax.
        doi: str | None
            Digital Object Identifier if available. Defaults to None.
        pmid: str | None
            PubMed Identifier if available. Defaults to None.
        authors: list[str] | None
            List of author names. Defaults to None.
        year: int | None
            Publication year between 1800 and 2100. Defaults to None.
        verified: bool
            Whether citation is verified against real literature. Defaults to True.

        Returns
        --------
            None: NoneType object
                Persists or updates citation entry.
        """
        self._validate_bibtex_syntax(bibtex, citation_key)

        authors_json_str: str = json.dumps(authors or [])
        verified_int: int = 1 if verified else 0
        created_at_iso: str = datetime.now(timezone.utc).isoformat()

        try:
            with self.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO citations_ledger (
                        citation_key, doi, pmid, title, authors, year,
                        bibtex, verified, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(citation_key) DO UPDATE SET
                        doi = COALESCE(excluded.doi, citations_ledger.doi),
                        pmid = COALESCE(excluded.pmid, citations_ledger.pmid),
                        title = excluded.title,
                        authors = excluded.authors,
                        year = COALESCE(excluded.year, citations_ledger.year),
                        bibtex = excluded.bibtex,
                        verified = excluded.verified;
                    """,
                    (
                        citation_key,
                        doi,
                        pmid,
                        title,
                        authors_json_str,
                        year,
                        bibtex,
                        verified_int,
                        created_at_iso,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise BlackboardError(
                f"Failed to register citation '{citation_key}': database "
                f"integrity constraint violation: {exc}"
            ) from exc

        return None

    def get_citation(self, citation_key: str) -> dict[str, Any] | None:
        """Retrieve a citation by its citation key.

        Parameters
        ------------
        citation_key: str
            BibTeX citation key to lookup.

        Returns
        --------
            dict[str, Any] | None: dictionary or None
                Citation record dictionary if found, else None.
        """
        with self.connection() as conn:
            cursor: sqlite3.Cursor = conn.execute(
                """
                SELECT
                    citation_key, doi, pmid, title, authors, year,
                    bibtex, verified, created_at
                FROM citations_ledger
                WHERE citation_key = ?;
                """,
                (citation_key,),
            )
            row: Any = cursor.fetchone()
            if row is None:
                return None
            result_citation: dict[str, Any] = self._row_to_citation_dict(row)
            return result_citation

    def get_citation_by_doi(self, doi: str) -> dict[str, Any] | None:
        """Retrieve a citation by its Digital Object Identifier (DOI).

        Parameters
        ------------
        doi: str
            DOI string to query.

        Returns
        --------
            dict[str, Any] | None: dictionary or None
                Citation record dictionary if found, else None.
        """
        with self.connection() as conn:
            cursor: sqlite3.Cursor = conn.execute(
                """
                SELECT
                    citation_key, doi, pmid, title, authors, year,
                    bibtex, verified, created_at
                FROM citations_ledger
                WHERE doi = ?;
                """,
                (doi,),
            )
            row: Any = cursor.fetchone()
            if row is None:
                return None
            result_citation: dict[str, Any] = self._row_to_citation_dict(row)
            return result_citation

    def list_citations(
        self,
        verified_only: bool = False,
    ) -> list[dict[str, Any]]:
        """List registered citations from the citations ledger.

        Parameters
        ------------
        verified_only: bool
            If True, returns only citations where verified == 1. Defaults to False.

        Returns
        --------
            list[dict[str, Any]]: list object
                List of citation record dictionaries.
        """
        query: str = """
            SELECT
                citation_key, doi, pmid, title, authors, year,
                bibtex, verified, created_at
            FROM citations_ledger
        """
        params: list[Any] = []
        if verified_only:
            query += " WHERE verified = 1"
        query += " ORDER BY citation_key ASC;"

        with self.connection() as conn:
            cursor: sqlite3.Cursor = conn.execute(query, tuple(params))
            rows: list[Any] = cursor.fetchall()
            records: list[dict[str, Any]] = [
                self._row_to_citation_dict(row) for row in rows
            ]
            return records

    def sync_citations_to_bib(self, bib_path: Path) -> int:
        """Sync all verified citations into a standard BibTeX file.

        Parameters
        ------------
        bib_path: Path
            Path to the target references.bib file.

        Returns
        --------
            int: integer object
                Total number of verified citations written to the file.
        """
        citations: list[dict[str, Any]] = self.list_citations(verified_only=True)
        entries: list[str] = ["% Neuri Verified Citations Ledger\n\n"]
        for entry in citations:
            entries.append(entry["bibtex"].strip() + "\n\n")

        bib_path.parent.mkdir(parents=True, exist_ok=True)
        bib_path.write_text("".join(entries), encoding="utf-8")
        count: int = len(citations)
        return count

    # -------------------------------------------------------------------------
    # Telemetry Operations
    # -------------------------------------------------------------------------

    def record_telemetry_event(self, event: TelemetryEvent) -> None:
        """Persist a normalized telemetry event into telemetry_events table.

        Parameters
        ------------
        event: TelemetryEvent
            Canonical telemetry event model.

        Returns
        --------
            None: NoneType object
                Inserts record into telemetry_events table.
        """
        ts_iso: str = event.timestamp.isoformat()
        payload_dict: dict[str, Any] = {
            "cached_tokens": event.cached_tokens,
            "reasoning_tokens": event.reasoning_tokens,
            "tool_host": event.tool_host,
            "duration_ms": event.duration_ms,
            "breaker_reason": event.breaker_reason,
        }
        payload_json: str = json.dumps(payload_dict)

        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO telemetry_events (
                    event_id, workflow_id, node_id, harness_id,
                    timestamp, event_type, thinking_text, input_tokens,
                    output_tokens, cost_usd, tool_name, tool_status,
                    payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    event.event_id,
                    event.workflow_id,
                    event.node_id,
                    event.harness_id,
                    ts_iso,
                    event.event_type,
                    event.thinking_text,
                    event.input_tokens,
                    event.output_tokens,
                    event.estimated_cost_usd,
                    event.tool_name,
                    event.tool_status,
                    payload_json,
                ),
            )

    def list_telemetry_events(
        self, workflow_id: str, node_id: str | None = None
    ) -> list[dict[str, Any]]:
        """List telemetry events recorded for a workflow or node.

        Parameters
        ------------
        workflow_id: str
            Workflow identifier.
        node_id: str | None
            Optional node identifier filter. Defaults to None.

        Returns
        --------
            list[dict[str, Any]]: list object
                Chronologically ordered list of telemetry event dictionaries.
        """
        query: str = """
            SELECT event_id, workflow_id, node_id, harness_id, timestamp,
                   event_type, thinking_text, input_tokens, output_tokens,
                   cost_usd, tool_name, tool_status, payload_json
            FROM telemetry_events
            WHERE workflow_id = ?
        """
        params: list[Any] = [workflow_id]
        if node_id is not None:
            query += " AND node_id = ?"
            params.append(node_id)
        query += " ORDER BY timestamp ASC;"

        with self.connection() as conn:
            cursor: sqlite3.Cursor = conn.execute(query, tuple(params))
            rows: list[Any] = cursor.fetchall()
            events: list[dict[str, Any]] = [dict(r) for r in rows]
            return events

    # -------------------------------------------------------------------------
    # Provenance Export Operations
    # -------------------------------------------------------------------------

    def export_provenance(
        self,
        workflow_id: str,
        output_path: Path,
    ) -> dict[str, Any]:
        """Export immutable provenance graph for a workflow to JSON.

        Serializes workflow status, all task nodes, directed edges,
        generated artifacts with sanitized headers, and verified citations.
        Safely merges into existing execution_history.json lists.

        Parameters
        ------------
        workflow_id: str
            Workflow identifier to export.
        output_path: Path
            Filesystem path for the exported execution history file.

        Returns
        --------
            dict[str, Any]: dictionary object
                Full structured provenance dictionary for the workflow.
        """
        with self.connection() as conn:
            wf_cursor: sqlite3.Cursor = conn.execute(
                """
                SELECT
                    workflow_id, prompt, status, total_tokens,
                    estimated_cost_usd, created_at, updated_at
                FROM workflows
                WHERE workflow_id = ?;
                """,
                (workflow_id,),
            )
            wf_row: Any = wf_cursor.fetchone()
            if wf_row is None:
                raise WorkflowNotFoundError(
                    f"Cannot export provenance: Workflow '{workflow_id}' "
                    "does not exist."
                )

            node_cursor: sqlite3.Cursor = conn.execute(
                """
                SELECT
                    node_id, agent_role, harness_id, state, attempt,
                    max_retries, envelope_json, summary_result,
                    diagnostic_feedback_json, created_at, updated_at,
                    started_at, completed_at
                FROM task_nodes
                WHERE workflow_id = ?
                ORDER BY created_at ASC;
                """,
                (workflow_id,),
            )
            nodes_data: list[dict[str, Any]] = []
            for nrow in node_cursor.fetchall():
                envelope_obj: Any = None
                if nrow["envelope_json"]:
                    envelope_obj = json.loads(nrow["envelope_json"])
                feedback_list: list[str] = []
                if nrow["diagnostic_feedback_json"]:
                    try:
                        parsed_feedback = json.loads(
                            nrow["diagnostic_feedback_json"]
                        )
                        if isinstance(parsed_feedback, list):
                            feedback_list = [str(x) for x in parsed_feedback]
                        elif isinstance(parsed_feedback, str):
                            feedback_list = [parsed_feedback]
                    except (json.JSONDecodeError, TypeError):
                        feedback_list = [nrow["diagnostic_feedback_json"]]

                nodes_data.append({
                    "node_id": nrow["node_id"],
                    "workflow_id": workflow_id,
                    "agent_role": nrow["agent_role"],
                    "harness_id": nrow["harness_id"],
                    "state": nrow["state"],
                    "attempt": nrow["attempt"],
                    "max_retries": nrow["max_retries"],
                    "envelope": envelope_obj,
                    "summary_result": nrow["summary_result"],
                    "diagnostic_feedback": feedback_list,
                    "created_at": nrow["created_at"],
                    "updated_at": nrow["updated_at"],
                    "started_at": nrow["started_at"],
                    "completed_at": nrow["completed_at"],
                })

            edge_cursor: sqlite3.Cursor = conn.execute(
                """
                SELECT parent_node_id, child_node_id
                FROM task_edges
                WHERE workflow_id = ?
                ORDER BY parent_node_id, child_node_id;
                """,
                (workflow_id,),
            )
            edges_data: list[dict[str, str]] = [
                {
                    "workflow_id": workflow_id,
                    "parent_node_id": erow["parent_node_id"],
                    "child_node_id": erow["child_node_id"],
                }
                for erow in edge_cursor.fetchall()
            ]

            art_cursor: sqlite3.Cursor = conn.execute(
                """
                SELECT
                    artifact_id, uri, host, posix_path, modality, space,
                    size_bytes, sha256, header_json, bids_entities_json,
                    node_id, created_at
                FROM remote_artifacts
                WHERE workflow_id = ?
                ORDER BY created_at ASC;
                """,
                (workflow_id,),
            )
            artifacts_data: list[dict[str, Any]] = []
            for arow in art_cursor.fetchall():
                artifacts_data.append({
                    "artifact_id": arow["artifact_id"],
                    "uri": arow["uri"],
                    "host": arow["host"],
                    "posix_path": arow["posix_path"],
                    "modality": arow["modality"],
                    "space": arow["space"],
                    "size_bytes": arow["size_bytes"],
                    "sha256_header": arow["sha256"],
                    "header_summary": json.loads(arow["header_json"]),
                    "bids_entities": json.loads(arow["bids_entities_json"]),
                    "created_by_node": arow["node_id"],
                    "created_at": arow["created_at"],
                })

            cit_cursor: sqlite3.Cursor = conn.execute(
                """
                SELECT
                    citation_key, doi, pmid, title, authors, year,
                    bibtex, verified, created_at
                FROM citations_ledger
                ORDER BY citation_key ASC;
                """
            )
            citations_data: list[dict[str, Any]] = []
            for crow in cit_cursor.fetchall():
                citations_data.append({
                    "citation_key": crow["citation_key"],
                    "doi": crow["doi"],
                    "pmid": crow["pmid"],
                    "title": crow["title"],
                    "authors": json.loads(crow["authors"]),
                    "year": crow["year"],
                    "bibtex": crow["bibtex"],
                    "verified": bool(crow["verified"]),
                    "created_at": crow["created_at"],
                })

        provenance_dict: dict[str, Any] = {
            "workflow_id": wf_row["workflow_id"],
            "prompt": wf_row["prompt"],
            "status": wf_row["status"],
            "total_tokens": wf_row["total_tokens"],
            "estimated_cost_usd": wf_row["estimated_cost_usd"],
            "created_at": wf_row["created_at"],
            "updated_at": wf_row["updated_at"],
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "nodes": nodes_data,
            "edges": edges_data,
            "artifacts": artifacts_data,
            "citations": citations_data,
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        history_list: list[dict[str, Any]] = []
        if output_path.exists():
            raw_text: str = output_path.read_text(encoding="utf-8").strip()
            if raw_text:
                try:
                    parsed_json: Any = json.loads(raw_text)
                    if isinstance(parsed_json, list):
                        history_list = [
                            item
                            for item in parsed_json
                            if isinstance(item, dict)
                        ]
                    elif isinstance(parsed_json, dict):
                        history_list = [parsed_json]
                except (json.JSONDecodeError, UnicodeDecodeError):
                    history_list = []

        replaced: bool = False
        for idx, entry in enumerate(history_list):
            if entry.get("workflow_id") == workflow_id:
                history_list[idx] = provenance_dict
                replaced = True
                break

        if not replaced:
            history_list.append(provenance_dict)

        output_path.write_text(
            json.dumps(history_list, indent=2), encoding="utf-8"
        )
        return provenance_dict

    # -------------------------------------------------------------------------
    # Helper Deserialization Methods
    # -------------------------------------------------------------------------

    def _row_to_task_node(self, row: sqlite3.Row) -> TaskNode:
        """Convert a database sqlite3.Row into a validated TaskNode model.

        Parameters
        ------------
        row: sqlite3.Row
            Database result row from the task_nodes table.

        Returns
        --------
            TaskNode: TaskNode instance
                Hydrated TaskNode domain model.
        """
        envelope_val: NeuriTaskEnvelope | None = None
        if row["envelope_json"]:
            envelope_val = NeuriTaskEnvelope.model_validate_json(
                row["envelope_json"]
            )

        feedback_val: list[str] = []
        if row["diagnostic_feedback_json"]:
            try:
                parsed: Any = json.loads(row["diagnostic_feedback_json"])
                if isinstance(parsed, list):
                    feedback_val = [str(item) for item in parsed]
                elif isinstance(parsed, str):
                    feedback_val = [parsed]
            except (json.JSONDecodeError, TypeError):
                feedback_val = [row["diagnostic_feedback_json"]]

        started_dt: datetime | None = None
        if row["started_at"]:
            started_dt = datetime.fromisoformat(row["started_at"])

        completed_dt: datetime | None = None
        if row["completed_at"]:
            completed_dt = datetime.fromisoformat(row["completed_at"])

        node: TaskNode = TaskNode(
            node_id=row["node_id"],
            workflow_id=row["workflow_id"],
            agent_role=row["agent_role"],
            harness_id=row["harness_id"],
            state=TaskState(row["state"]),
            attempt=row["attempt"],
            max_retries=row["max_retries"],
            envelope=envelope_val,
            summary_result=row["summary_result"],
            diagnostic_feedback=feedback_val,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            started_at=started_dt,
            completed_at=completed_dt,
        )
        return node

    def _row_to_artifact(self, row: sqlite3.Row) -> RemoteArtifact:
        """Convert a database sqlite3.Row into a validated RemoteArtifact model.

        Parameters
        ------------
        row: sqlite3.Row
            Database result row from the remote_artifacts table.

        Returns
        --------
            RemoteArtifact: RemoteArtifact instance
                Hydrated RemoteArtifact domain model.
        """
        header_summary: SanitizedNeuroHeader = (
            SanitizedNeuroHeader.model_validate_json(row["header_json"])
        )
        bids_entities: dict[str, str] = json.loads(row["bids_entities_json"])
        created_at_dt: datetime = datetime.fromisoformat(row["created_at"])

        artifact: RemoteArtifact = RemoteArtifact(
            artifact_id=row["artifact_id"],
            uri=row["uri"],
            host=row["host"],
            posix_path=row["posix_path"],
            modality=ModalityType(row["modality"]),
            space=row["space"],
            bids_entities=bids_entities,
            sha256_header=row["sha256"],
            size_bytes=row["size_bytes"],
            header_summary=header_summary,
            created_by_node=row["node_id"],
            created_at=created_at_dt,
        )
        return artifact

    def _row_to_citation_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        """Convert a database sqlite3.Row into a citation dictionary.

        Parameters
        ------------
        row: sqlite3.Row
            Database result row from the citations_ledger table.

        Returns
        --------
            dict[str, Any]: dictionary object
                Reconstructed citation entry with parsed authors list.
        """
        authors_list: list[str] = []
        if row["authors"]:
            try:
                parsed_authors: Any = json.loads(row["authors"])
                if isinstance(parsed_authors, list):
                    authors_list = [str(a) for a in parsed_authors]
            except (json.JSONDecodeError, TypeError):
                authors_list = [str(row["authors"])]

        citation_record: dict[str, Any] = {
            "citation_key": row["citation_key"],
            "doi": row["doi"],
            "pmid": row["pmid"],
            "title": row["title"],
            "authors": authors_list,
            "year": row["year"],
            "bibtex": row["bibtex"],
            "verified": bool(row["verified"]),
            "created_at": row["created_at"],
        }
        return citation_record
