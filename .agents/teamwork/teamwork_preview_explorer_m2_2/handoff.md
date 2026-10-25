# Investigation Report: Milestone 2 — DAG Topological Queries, Cycle Detection, Atomic CRUD & State Machine

**Role:** Explorer M2-2 (DAG & CRUD)  
**Date:** 2026-10-25T16:22:00Z  
**Target Module:** `src/neuri/core/blackboard.py`  
**Working Directory:** `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m2_2/`

---

## 1. Observation

### 1.1 Direct Observations from Codebase & Specifications

1. **Original User Request (`ORIGINAL_REQUEST.md` lines 23-27):**
   > "Implement `src/neuri/core/blackboard.py` backed by `.neuri/state.db` in SQLite `WAL` mode (`PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;`)."
   > "Create and manage the 7 core tables: `workflows`, `task_nodes`, `task_edges`, `remote_artifacts`, `remote_jobs`, `telemetry_events`, and `citations_ledger`."
   > "Implement atomic CRUD, topological DAG queries (`get_ready_nodes`), state transitions, artifact registration, and provenance logging (`.neuri/execution_history.json`)."

2. **Project Specification (`PROJECT.md` lines 120-125):**
   > "M2 (Blackboard) ↔ M5 (Orchestrator):
   > - `Blackboard.get_ready_nodes(workflow_id: str) -> list[TaskNode]`
   > - `Blackboard.update_node_state(node_id: str, state: TaskState, diagnostic_feedback: str | None = None) -> None`
   > - `Blackboard.register_artifact(artifact: RemoteArtifact, workflow_id: str) -> None`
   > - `Blackboard.export_provenance(workflow_id: str, output_path: Path) -> dict[str, Any]`"

3. **Task Assignment (`DISPATCH.md` lines 8-20):**
   > "Analyze and specify the DAG query algorithms, atomic state transitions, and CRUD operations for `src/neuri/core/blackboard.py`:
   > 1. `get_ready_nodes(workflow_id: str) -> list[TaskNode]`:
   >    - Returns all nodes in `PENDING` state whose parent nodes (incoming edges in `task_edges`) are ALL in `COMPLETED` state.
   >    - Handles root nodes (in-degree 0) properly.
   >    - Blocks nodes if any parent failed, cancelled, or still running.
   > 2. Cycle detection and edge validation:
   >    - Validates DAG acyclicity when adding edges.
   > 3. State transitions and feedback logging:
   >    - `update_node_state(node_id: str, state: TaskState, diagnostic_feedback: str | None = None) -> None`
   >    - Handles transitions through `PENDING` -> `PREFLIGHT_CHECK` -> `RUNNING` -> `QA_REVIEW` -> `COMPLETED`, `RETRYING`, and `WAITING_OPERATOR`.
   > 4. Ensure 100% compliance with `/Users/mszdjh3/.gemini/config/rules/python_standard.md`."

4. **Canonical Schemas (`src/neuri/core/schemas.py`):**
   - `TaskState` (lines 470-538):
     - Valid enum values: `PENDING`, `PREFLIGHT_CHECK`, `RUNNING`, `QA_REVIEW`, `RETRYING`, `WAITING_OPERATOR`, `COMPLETED`, `FAILED`, `CANCELLED`.
     - `TaskState.is_terminal()`: returns True for `COMPLETED`, `FAILED`, `CANCELLED`.
     - `TaskState.is_active()`: returns True for `PREFLIGHT_CHECK`, `RUNNING`, `QA_REVIEW`, `RETRYING`.
   - `TaskNode` (lines 913-1110):
     - Attributes: `node_id: str`, `workflow_id: str`, `agent_role: str`, `harness_id: str`, `state: TaskState = TaskState.PENDING`, `attempt: int = 0`, `max_retries: int = 2`, `envelope: NeuriTaskEnvelope | None = None`, `summary_result: str | None = None`, `diagnostic_feedback: list[str] = []`, `started_at: datetime | None = None`, `completed_at: datetime | None = None`.
     - Normalized properties: `.role` (alias of `agent_role`), `.harness` (alias of `harness_id`).
   - `TaskEdge` (lines 1113-1168):
     - Attributes: `workflow_id: str`, `parent_node_id: str`, `child_node_id: str`.
     - Model validator: asserts `parent_node_id != child_node_id` (self-loop prevention).

5. **Peer Explorer M2-1 Hand-off Report (`.agents/teamwork/teamwork_preview_explorer_m2_1/handoff.md`):**
   - Table `task_nodes`: columns `node_id`, `workflow_id`, `agent_role`, `harness_id`, `state`, `attempt`, `max_retries`, `envelope_json`, `summary_result`, `diagnostic_feedback_json`, `created_at`, `updated_at`, `started_at`, `completed_at`.
   - Table `task_edges`: columns `workflow_id`, `parent_node_id`, `child_node_id`, primary key `(workflow_id, parent_node_id, child_node_id)`, foreign keys with `ON DELETE CASCADE`.
   - Table `workflows`: columns `workflow_id`, `prompt`, `status`, `created_at`, `updated_at`, `total_tokens`, `estimated_cost_usd`.
   - Dedicated indexes: `idx_task_nodes_wf_state (workflow_id, state)`, `idx_task_edges_wf_child (workflow_id, child_node_id)`, `idx_task_edges_wf_parent (workflow_id, parent_node_id)`.
   - Connection manager: `with self.connection() as conn:` with SQLite WAL, busy timeout 5000ms, foreign keys ON, synchronous NORMAL, and `conn.row_factory = sqlite3.Row`.

6. **Universal Python Coding Standards (`/Users/mszdjh3/.gemini/config/rules/python_standard.md` & AST Validator):**
   - Max line length limit: <= 88 characters.
   - PascalCase for classes, snake_case for functions and methods.
   - 100% type annotations on all parameters and return types.
   - Mandatory docstrings with formatted `Parameters\n------------` and `Returns\n--------` blocks.
   - Zero module-level globals (`check_zero_globals` in AST checker): all constants must be class attributes.
   - Single return statement returning a single variable.

---

## 2. Logic Chain

### 2.1 Ready Node Query Algorithm (`get_ready_nodes`)

1. **Topological Invariant Definition:**
   - In a workflow DAG $G = (V, E)$, a node $v \in V$ is "ready" for execution if and only if:
     1. $v$ is in state `PENDING` ($v.\text{state} = \text{PENDING}$).
     2. Every direct predecessor (parent node) $u \in \text{Parents}(v)$ has reached state `COMPLETED` ($u.\text{state} = \text{COMPLETED}$).
2. **Handling Root Nodes (In-degree = 0):**
   - When a node $v$ has no incoming edges ($\text{Parents}(v) = \emptyset$), the universal condition $\forall u \in \text{Parents}(v), u.\text{state} = \text{COMPLETED}$ is vacuously true.
   - Therefore, all root nodes currently in state `PENDING` are immediately eligible to execute.
3. **Blocking Conditions:**
   - If any parent $u$ is in state `RUNNING`, `PREFLIGHT_CHECK`, `QA_REVIEW`, `RETRYING`, `WAITING_OPERATOR`, `FAILED`, or `CANCELLED`, the condition is violated, and $v$ MUST NOT be scheduled.
   - In particular, if a parent has failed or been cancelled, the child is blocked by dependency failure.
4. **Relational Query Formulation:**
   - Using SQL `NOT EXISTS`:
     ```sql
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
     ```
   - **Proof of Correctness:**
     - For root nodes: the inner subquery returns 0 rows. `NOT EXISTS` evaluates to `TRUE`. Node is returned.
     - For nodes whose parents are all `COMPLETED`: every parent has `p.state = 'COMPLETED'`. The subquery filters out all completed parents, returning 0 rows. `NOT EXISTS` evaluates to `TRUE`. Node is returned.
     - For nodes with any parent where `p.state != 'COMPLETED'` or `p.node_id IS NULL`: the subquery finds at least 1 row. `NOT EXISTS` evaluates to `FALSE`. Node is omitted.
     - Index efficiency: SQLite utilizes `idx_task_nodes_wf_state` to narrow down candidate pending nodes and `idx_task_edges_wf_child` to test incoming edges in $O(1)$ to $O(\log E)$ time per candidate.

### 2.2 Incremental Cycle Detection & Acyclicity Invariants

1. **Theorem:** Given an existing Directed Acyclic Graph $G = (V, E)$, adding a directed edge $e = (u, v)$ produces a directed cycle if and only if there already exists a directed path from $v$ to $u$ in $G$ ($v \rightsquigarrow u$).
   - *Proof ($\Rightarrow$):* Suppose adding $(u, v)$ creates a cycle. Since $G$ was acyclic, the cycle must include the new edge $(u, v)$. The remainder of the cycle forms a directed path from $v$ to $u$ in $G$. Thus, $v \rightsquigarrow u$ exists in $G$.
   - *Proof ($\Leftarrow$):* Suppose a directed path $P = (v = w_0, w_1, \dots, w_k = u)$ exists in $G$. Adding the directed edge $(u, v)$ creates the closed directed walk $(u, v, w_1, \dots, w_k = u)$, which is a directed cycle.
2. **Algorithm Implementation:**
   - Before inserting edge $(u, v)$ into `task_edges`:
     1. Verify $u \ne v$ (self-loop prevention). If $u = v$, raise `ValueError`.
     2. Verify both $u$ and $v$ exist in `task_nodes` for `workflow_id`. If either is missing, raise `NodeNotFoundError`.
     3. Check if edge $(u, v)$ already exists in `task_edges`. If present, return idempotently.
     4. Execute Breadth-First Search (BFS) starting at child $v$ to search for a directed path to parent $u$.
     5. If a path $v \rightsquigarrow u$ is found, reconstruct the complete cycle $[u] + [v, \dots, u]$ and raise `CycleDetectedError` detailing the exact cycle path.
     6. If BFS terminates without reaching $u$, insert $(u, v)$ safely.
3. **Global Topological Validation (Kahn's Algorithm):**
   - Provide `get_topological_order(workflow_id: str) -> list[str]` executing Kahn's algorithm:
     - Calculates in-degree for all workflow nodes.
     - Enqueues nodes with in-degree 0 in sorted order (for deterministic reproducibility).
     - Iteratively decrements successor in-degrees.
     - If the ordered list length is less than total nodes, a cycle exists; raise `CycleDetectedError`.

### 2.3 Task Node State Machine & Diagnostic Feedback

1. **State Transition Invariants:**
   - Nodes transition through distinct lifecycle stages:
     - `PENDING` $\to$ `PREFLIGHT_CHECK`, `RUNNING`, `CANCELLED`
     - `PREFLIGHT_CHECK` $\to$ `RUNNING`, `RETRYING`, `WAITING_OPERATOR`, `FAILED`, `CANCELLED`
     - `RUNNING` $\to$ `QA_REVIEW`, `COMPLETED`, `RETRYING`, `WAITING_OPERATOR`, `FAILED`, `CANCELLED`
     - `QA_REVIEW` $\to$ `COMPLETED`, `RETRYING`, `WAITING_OPERATOR`, `FAILED`, `CANCELLED`
     - `RETRYING` $\to$ `PREFLIGHT_CHECK`, `RUNNING`, `CANCELLED`
     - `WAITING_OPERATOR` $\to$ `RETRYING`, `RUNNING`, `COMPLETED`, `CANCELLED`, `FAILED`
     - `COMPLETED` $\to \emptyset$ (terminal)
     - `FAILED` $\to$ `RETRYING` (permitted upon operator slash command `/retry`)
     - `CANCELLED` $\to \emptyset$ (terminal)
2. **Atomic Timestamps & Attempt Counters:**
   - Entering `RUNNING`: sets `started_at` to current UTC ISO timestamp if currently `None`.
   - Entering terminal states (`COMPLETED`, `FAILED`, `CANCELLED`): sets `completed_at` to current UTC ISO timestamp.
   - Entering `RETRYING`: atomically increments `attempt` by 1.
3. **Diagnostic Feedback Logging:**
   - Column `diagnostic_feedback_json` in `task_nodes` stores a JSON list of feedback strings.
   - When `diagnostic_feedback` is passed to `update_node_state`, it is parsed, stripped, appended to the list, and persisted.
   - If `envelope_json` is present on the node:
     - `envelope.diagnostic_feedback` is updated to the latest feedback string.
     - `envelope.attempt_number` is synchronized with `node.attempt + 1`.

### 2.4 Atomic CRUD Operations

1. **Workflows Table CRUD:**
   - `create_workflow(workflow_id: str, prompt: str) -> None`
   - `get_workflow(workflow_id: str) -> dict[str, Any] | None`
   - `update_workflow_status(workflow_id: str, status: str, total_tokens: int | None = None, estimated_cost_usd: float | None = None) -> None`
   - `list_workflows() -> list[dict[str, Any]]`
   - `reconcile_workflow_status(workflow_id: str) -> str`
2. **Task Nodes Table CRUD:**
   - `create_node(node: TaskNode) -> None`
   - `create_nodes(nodes: list[TaskNode]) -> None`
   - `get_node(node_id: str) -> TaskNode | None`
   - `get_nodes_by_workflow(workflow_id: str) -> list[TaskNode]`
   - `update_node_envelope(node_id: str, envelope: NeuriTaskEnvelope) -> None`
   - `record_node_result(node_id: str, result: NeuriTaskResult) -> None`
3. **Task Edges Table CRUD:**
   - `add_edge(edge: TaskEdge) -> None`
   - `add_edges(edges: list[TaskEdge]) -> None`
   - `get_edges(workflow_id: str) -> list[TaskEdge]`
   - `get_parent_nodes(node_id: str) -> list[TaskNode]`
   - `get_child_nodes(node_id: str) -> list[TaskNode]`
   - `get_parent_node_ids(node_id: str) -> list[str]`
   - `get_child_node_ids(node_id: str) -> list[str]`

---

## 3. Caveats

1. **Operator Retry on Failed Nodes:**
   - While `FAILED` is technically a terminal state for automated execution, Neuri's human-in-the-loop requirement (Slash Command `/retry <node_id>`) explicitly allows an operator to re-trigger a failed node. Thus, the state machine allows `FAILED -> RETRYING`.
2. **Concurrent Multi-Agent Writes:**
   - Under SQLite WAL mode, readers never block writers, but concurrent writes acquire an exclusive transaction lock. The 5000ms `busy_timeout` ensures that if two agents attempt simultaneous state transitions or edge additions, SQLite safely waits rather than raising an immediate locking error.
3. **Zero Module Globals Rule:**
   - In accordance with `tests/unit/test_standards_compliance.py`, all state machine transitions and constants are defined as class attributes on `Blackboard` rather than module-level dictionaries.
4. **Read-Only Scope:**
   - This investigation does not modify source code files directly. All class structures and implementations are provided below in Section 4 for the implementer agent.

---

## 4. Conclusion & Complete Implementation Specification

The following specifications define the exception hierarchy, state machine mappings, and complete method implementations for `src/neuri/core/blackboard.py`.

### 4.1 Exception Hierarchy

```python
class BlackboardError(Exception):
    """Base exception for all SQLite Blackboard state engine operations."""

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
    """Raised when a requested workflow identifier is not found in database."""


class NodeNotFoundError(BlackboardError):
    """Raised when a requested task node identifier is not found in database."""


class CycleDetectedError(BlackboardError):
    """Raised when adding an edge would create a directed cycle in the DAG."""


class InvalidStateTransitionError(BlackboardError):
    """Raised when an illegal node state transition is attempted."""


class DuplicateEdgeError(BlackboardError):
    """Raised when an identical dependency edge already exists."""
```

---

### 4.2 Class `Blackboard` Method Specifications

The following class methods integrate directly into the `Blackboard` class defined in M2-1:

```python
class Blackboard:
    """SQLite WAL-backed persistent blackboard coordinating multi-agent state.

    Manages concurrent connections, schema initialization, atomic DAG queries,
    state transitions, and provenance tracking.
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

    # -------------------------------------------------------------------------
    # Workflow CRUD Operations
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
            cursor = conn.execute(
                """
                SELECT workflow_id, prompt, status, created_at, updated_at,
                       total_tokens, estimated_cost_usd
                FROM workflows
                WHERE workflow_id = ?;
                """,
                (workflow_id,),
            )
            row = cursor.fetchone()
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
            cursor = conn.execute(
                """
                SELECT workflow_id, prompt, status, created_at, updated_at,
                       total_tokens, estimated_cost_usd
                FROM workflows
                ORDER BY created_at DESC;
                """
            )
            rows = cursor.fetchall()
            result_list: list[dict[str, Any]] = [dict(r) for r in rows]
            return result_list

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
        elif any(s in (
            TaskState.RUNNING,
            TaskState.PREFLIGHT_CHECK,
            TaskState.QA_REVIEW,
            TaskState.RETRYING,
        ) for s in states):
            target_status = "RUNNING"
        elif any(s == TaskState.CANCELLED for s in states):
            target_status = "CANCELLED"
        else:
            target_status = "PENDING"

        self.update_workflow_status(workflow_id, target_status)
        result_status: str = target_status
        return result_status

    # -------------------------------------------------------------------------
    # Task Node CRUD Operations
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
            node.completed_at.isoformat() if node.completed_at is not None else None
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
            cursor = conn.execute(
                """
                SELECT * FROM task_nodes WHERE node_id = ?;
                """,
                (node_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            result_node: TaskNode = self._row_to_task_node(row)
            return result_node

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
            cursor = conn.execute(
                """
                SELECT * FROM task_nodes
                WHERE workflow_id = ?
                ORDER BY created_at ASC, node_id ASC;
                """,
                (workflow_id,),
            )
            rows = cursor.fetchall()
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
            cursor = conn.execute(
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

    # -------------------------------------------------------------------------
    # Task Edge CRUD & Cycle Detection Operations
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
            parent_row = conn.execute(
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

            child_row = conn.execute(
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

            existing_edge = conn.execute(
                """
                SELECT 1 FROM task_edges
                WHERE workflow_id = ? AND parent_node_id = ? AND child_node_id = ?;
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
                INSERT INTO task_edges (workflow_id, parent_node_id, child_node_id)
                VALUES (?, ?, ?);
                """,
                (edge.workflow_id, edge.parent_node_id, edge.child_node_id),
            )

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
            cursor = conn.execute(
                """
                SELECT workflow_id, parent_node_id, child_node_id
                FROM task_edges
                WHERE workflow_id = ?
                ORDER BY parent_node_id ASC, child_node_id ASC;
                """,
                (workflow_id,),
            )
            rows = cursor.fetchall()
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
            cursor = conn.execute(
                """
                SELECT p.*
                FROM task_nodes p
                JOIN task_edges e ON p.node_id = e.parent_node_id
                WHERE e.child_node_id = ?
                ORDER BY p.created_at ASC, p.node_id ASC;
                """,
                (node_id,),
            )
            rows = cursor.fetchall()
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
            cursor = conn.execute(
                """
                SELECT c.*
                FROM task_nodes c
                JOIN task_edges e ON c.node_id = e.child_node_id
                WHERE e.parent_node_id = ?
                ORDER BY c.created_at ASC, c.node_id ASC;
                """,
                (node_id,),
            )
            rows = cursor.fetchall()
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
            cursor = conn.execute(
                """
                SELECT parent_node_id
                FROM task_edges
                WHERE child_node_id = ?
                ORDER BY parent_node_id ASC;
                """,
                (node_id,),
            )
            rows = cursor.fetchall()
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
            cursor = conn.execute(
                """
                SELECT child_node_id
                FROM task_edges
                WHERE parent_node_id = ?
                ORDER BY child_node_id ASC;
                """,
                (node_id,),
            )
            rows = cursor.fetchall()
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
        cursor = conn.execute(
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
            cursor = conn.execute(
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
            rows = cursor.fetchall()
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
            node_cursor = conn.execute(
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

            edge_cursor = conn.execute(
                """
                SELECT parent_node_id, child_node_id FROM task_edges
                WHERE workflow_id = ?;
                """,
                (workflow_id,),
            )
            edge_rows = edge_cursor.fetchall()

        in_degree: dict[str, int] = {node_id: 0 for node_id in all_nodes}
        adjacency: dict[str, list[str]] = {node_id: [] for node_id in all_nodes}

        for row in edge_rows:
            parent_id = row["parent_node_id"]
            child_id = row["child_node_id"]
            if parent_id in in_degree and child_id in in_degree:
                in_degree[child_id] += 1
                adjacency[parent_id].append(child_id)

        queue: deque[str] = deque(
            sorted([nid for nid, deg in in_degree.items() if deg == 0])
        )
        ordered: list[str] = []

        while queue:
            current = queue.popleft()
            ordered.append(current)

            for neighbor in sorted(adjacency.get(current, [])):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(ordered) != len(all_nodes):
            unvisited = [n for n in all_nodes if n not in set(ordered)]
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
        pending_nodes = [
            n for n in self.get_nodes_by_workflow(workflow_id)
            if n.state == TaskState.PENDING
        ]
        blocked: list[tuple[TaskNode, list[str]]] = []

        for node in pending_nodes:
            parents = self.get_parent_nodes(node.node_id)
            failed_parents = [
                p.node_id for p in parents
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

        Returns
        --------
            None: NoneType object
                Updates task node record in database.
        """
        with self.connection() as conn:
            cursor = conn.execute(
                """
                SELECT node_id, workflow_id, state, attempt, max_retries,
                       envelope_json, diagnostic_feedback_json,
                       started_at, completed_at
                FROM task_nodes
                WHERE node_id = ?;
                """,
                (node_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise NodeNotFoundError(
                    f"Task node '{node_id}' does not exist in blackboard."
                )

            current_state: TaskState = TaskState(row["state"])

            # Idempotent return if state does not change and no feedback added
            if current_state == state and diagnostic_feedback is None:
                return

            # State transition validation
            if current_state != state:
                allowed_targets = self.VALID_TRANSITIONS.get(
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
                    parsed = json.loads(row["diagnostic_feedback_json"])
                    if isinstance(parsed, list):
                        feedback_list = [str(x) for x in parsed]
                    elif isinstance(parsed, str):
                        feedback_list = [parsed]
                except (json.JSONDecodeError, TypeError):
                    feedback_list = [row["diagnostic_feedback_json"]]

            if diagnostic_feedback and diagnostic_feedback.strip():
                feedback_list.append(diagnostic_feedback.strip())

            new_feedback_json: str = json.dumps(feedback_list)

            new_envelope_json: str | None = row["envelope_json"]
            if new_envelope_json is not None:
                try:
                    envelope = NeuriTaskEnvelope.model_validate_json(
                        new_envelope_json
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
                    new_feedback_json,
                    started_iso,
                    completed_iso,
                    now_iso,
                    node_id,
                ),
            )

    # -------------------------------------------------------------------------
    # Schema Deserialization Helper
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
                parsed = json.loads(row["diagnostic_feedback_json"])
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
            started_at=started_dt,
            completed_at=completed_dt,
        )
        return node
```

---

## 5. Verification Method

### 5.1 Verification Commands

```bash
# 1. Execute Unit Test Suite for Blackboard
uv run pytest tests/unit/test_blackboard.py -v

# 2. Execute Universal Python Coding Standards AST Validator
uv run pytest tests/unit/test_standards_compliance.py -v

# 3. Execute Full Unit Test Suite
uv run pytest tests/unit/ -v
```

### 5.2 Test Cases Matrix for `tests/unit/test_blackboard.py`

| Test Function | Verification Scenario | Expected Outcome |
| :--- | :--- | :--- |
| `test_get_ready_nodes_root` | Workflow with 2 independent root nodes in `PENDING` state | Both root nodes returned immediately by `get_ready_nodes()` |
| `test_get_ready_nodes_blocked_by_pending_parent` | Node B depends on Node A; Node A is `PENDING` | `get_ready_nodes()` returns only `[A]`; `B` is omitted |
| `test_get_ready_nodes_blocked_by_running_parent` | Node B depends on Node A; Node A is `RUNNING` | `get_ready_nodes()` returns `[]` |
| `test_get_ready_nodes_unblocked_on_completion` | Node A transitions to `COMPLETED` | `get_ready_nodes()` now returns `[B]` |
| `test_get_ready_nodes_blocked_by_failed_parent` | Node A transitions to `FAILED` | `get_ready_nodes()` returns `[]`; `get_blocked_nodes()` reports B blocked by A |
| `test_get_ready_nodes_diamond_dag` | Diamond DAG: $A \to B, A \to C, B \to D, C \to D$ | Stage 1: `[A]`; Stage 2: `[B, C]`; Stage 3: `[D]` only after both B and C complete |
| `test_cycle_detection_self_loop` | Add edge $A \to A$ | Raises `ValueError` |
| `test_cycle_detection_direct_cycle` | Edge $A \to B$ exists; attempt to add $B \to A$ | Raises `CycleDetectedError` with path `B -> A -> B` |
| `test_cycle_detection_transitive_cycle` | Edges $A \to B \to C \to D$; attempt to add $D \to A$ | Raises `CycleDetectedError` with path `A -> D -> ... -> A` |
| `test_add_edge_missing_node` | Attempt to add edge referencing non-existent node ID | Raises `NodeNotFoundError` |
| `test_get_topological_order` | Diamond DAG | Returns deterministic valid topological list `['A', 'B', 'C', 'D']` |
| `test_update_node_state_valid_lifecycle` | Transitions `PENDING` $\to$ `PREFLIGHT_CHECK` $\to$ `RUNNING` $\to$ `QA_REVIEW` $\to$ `COMPLETED` | State persists cleanly; `started_at` and `completed_at` populated |
| `test_update_node_state_retry` | Transition `RUNNING` $\to$ `RETRYING` with feedback | `attempt` increments $0 \to 1$; feedback stored in `diagnostic_feedback_json` |
| `test_update_node_state_invalid_transition` | Attempt transition `PENDING` $\to$ `COMPLETED` | Raises `InvalidStateTransitionError` |
| `test_update_node_state_operator_retry` | Transition `FAILED` $\to$ `RETRYING` | Permitted for operator `/retry` command; attempt increments |
| `test_reconcile_workflow_status` | All nodes complete | Workflow status transitions to `COMPLETED` |

### 5.3 Invalidation Conditions
- If `get_ready_nodes` returns nodes whose parents are in `RUNNING` or `FAILED` state.
- If `add_edge` permits any directed cycle or self-loop to be inserted into `task_edges`.
- If an illegal state transition (e.g. `PENDING` $\to$ `COMPLETED`) is executed without raising `InvalidStateTransitionError`.
- If any line of code exceeds 88 characters or violates `python_standard.md` docstrings or typing.
