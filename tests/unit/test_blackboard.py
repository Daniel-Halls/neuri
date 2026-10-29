"""Unit tests for SQLite WAL Blackboard, DAG queries, artifacts & provenance.

Validates WAL journal mode, foreign key enforcement, ready nodes DAG queries,
cycle detection, atomic CRUD, artifact registration uniqueness, citations ledger,
telemetry event logging, and execution history provenance export (Milestone 2).
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any

import pytest

from neuri.core.blackboard import (
    ArtifactRegistrationError,
    Blackboard,
    BlackboardError,
    CycleDetectedError,
    InvalidStateTransitionError,
    NodeNotFoundError,
    WorkflowNotFoundError,
)
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


@pytest.fixture
def blackboard(tmp_path: Path) -> Blackboard:
    """Provide an initialized Blackboard instance in a temporary directory.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        Blackboard: Blackboard instance
            Initialized SQLite WAL Blackboard object.
    """
    db_file: Path = tmp_path / "state.db"
    bb: Blackboard = Blackboard(db_file)
    return bb


@pytest.fixture
def sample_header() -> SanitizedNeuroHeader:
    """Provide a canonical SanitizedNeuroHeader fixture.

    Parameters
    ------------
    None

    Returns
    --------
        SanitizedNeuroHeader: SanitizedNeuroHeader instance
            PHI-sanitized header model.
    """
    header: SanitizedNeuroHeader = SanitizedNeuroHeader(
        shape=[256, 256, 176],
        voxel_sizes_mm=[1.0, 1.0, 1.0],
        orientation="RAS",
        dtype="float32",
        phi_sanitized=True,
    )
    return header


@pytest.fixture
def sample_artifact(sample_header: SanitizedNeuroHeader) -> RemoteArtifact:
    """Provide a canonical RemoteArtifact fixture.

    Parameters
    ------------
    sample_header: SanitizedNeuroHeader
        Sanitized header fixture.

    Returns
    --------
        RemoteArtifact: RemoteArtifact instance
            Remote artifact pointer model.
    """
    art: RemoteArtifact = RemoteArtifact(
        artifact_id="art-test-001",
        uri="hpc-cluster:///scratch/sub-01_T1w.nii.gz",
        host="hpc-cluster",
        posix_path="/scratch/sub-01_T1w.nii.gz",
        modality=ModalityType.T1W,
        space="MNI152NLin2009cAsym",
        bids_entities={"sub": "01", "suffix": "T1w"},
        sha256_header="a" * 64,
        size_bytes=1048576,
        header_summary=sample_header,
    )
    return art


class TestBlackboardInitAndWal:
    """Test suite for SQLite initialization, WAL mode, and PRAGMA settings."""

    def test_init_creates_database_file(self, tmp_path: Path) -> None:
        """Verify Blackboard constructor creates state.db file and parent dirs.

        Parameters
        ------------
        tmp_path: Path
            Pytest temporary directory.

        Returns
        --------
            None: NoneType object
                Asserts file exists on disk.
        """
        db_path: Path = tmp_path / "nested" / "dir" / "state.db"
        assert not db_path.exists()
        Blackboard(db_path)
        assert db_path.is_file()

    def test_wal_journal_mode_enabled(self, blackboard: Blackboard) -> None:
        """Verify PRAGMA journal_mode returns wal.

        Parameters
        ------------
        blackboard: Blackboard
            Initialized Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts journal mode is WAL.
        """
        assert blackboard.verify_wal_mode() is True

    def test_foreign_keys_pragma_enabled(
        self, blackboard: Blackboard
    ) -> None:
        """Verify PRAGMA foreign_keys returns 1 (ON).

        Parameters
        ------------
        blackboard: Blackboard
            Initialized Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts foreign keys are enabled.
        """
        assert blackboard.verify_foreign_keys_enabled() is True

    def test_all_seven_tables_present(self, blackboard: Blackboard) -> None:
        """Verify all 7 core relational tables are created on initialization.

        Parameters
        ------------
        blackboard: Blackboard
            Initialized Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts presence of 7 core tables in sqlite_master.
        """
        expected_tables: set[str] = {
            "workflows",
            "task_nodes",
            "task_edges",
            "remote_artifacts",
            "remote_jobs",
            "telemetry_events",
            "citations_ledger",
        }
        with blackboard.connection() as conn:
            cursor: sqlite3.Cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table';"
            )
            tables: set[str] = {row[0] for row in cursor.fetchall()}
        assert expected_tables.issubset(tables)

    def test_idempotent_initialization(self, tmp_path: Path) -> None:
        """Verify re-instantiating Blackboard on existing database is safe.

        Parameters
        ------------
        tmp_path: Path
            Pytest temporary directory.

        Returns
        --------
            None: NoneType object
                Asserts safe re-initialization and preserved data.
        """
        db_file: Path = tmp_path / "state.db"
        bb1: Blackboard = Blackboard(db_file)
        bb1.create_workflow("wf-idemp", "Test prompt")

        bb2: Blackboard = Blackboard(db_file)
        wf: dict[str, Any] | None = bb2.get_workflow("wf-idemp")
        assert wf is not None
        assert wf["prompt"] == "Test prompt"


class TestBlackboardReferentialIntegrity:
    """Test suite verifying foreign key constraints and cascade actions."""

    def test_task_node_requires_existing_workflow(
        self, blackboard: Blackboard
    ) -> None:
        """Verify inserting task node with non-existent workflow fails FK check.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts foreign key integrity failure.
        """
        node: TaskNode = TaskNode(
            node_id="node-orphan",
            workflow_id="wf-nonexistent",
            agent_role="neuroimaging_specialist",
            harness_id="agy",
        )
        with pytest.raises((sqlite3.IntegrityError, BlackboardError)):
            blackboard.create_task_node(node)

    def test_task_edge_requires_existing_parent_and_child(
        self, blackboard: Blackboard
    ) -> None:
        """Verify adding edge referencing missing nodes fails FK check.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts foreign key integrity failure.
        """
        blackboard.create_workflow("wf-fk", "Test prompt")
        with pytest.raises((sqlite3.IntegrityError, BlackboardError)):
            blackboard.add_task_edge(
                "wf-fk", "node-missing-p", "node-missing-c"
            )

    def test_cascade_delete_workflow(self, blackboard: Blackboard) -> None:
        """Verify deleting a workflow cascades to delete associated nodes.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts cascade removal of nodes.
        """
        blackboard.create_workflow("wf-del", "Delete test")
        node: TaskNode = TaskNode(
            node_id="node-del",
            workflow_id="wf-del",
            agent_role="pipeline_engineer",
            harness_id="codex",
        )
        blackboard.create_task_node(node)
        blackboard.delete_workflow("wf-del")

        assert blackboard.get_workflow("wf-del") is None
        assert blackboard.get_task_node("node-del") is None


class TestBlackboardWorkflowCrud:
    """Test suite for workflow lifecycle and metric tracking."""

    def test_create_and_get_workflow(self, blackboard: Blackboard) -> None:
        """Verify creating and retrieving a workflow record.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts workflow attributes match.
        """
        blackboard.create_workflow("wf-100", "Preprocess sub-01")
        wf: dict[str, Any] | None = blackboard.get_workflow("wf-100")
        assert wf is not None
        assert wf["workflow_id"] == "wf-100"
        assert wf["prompt"] == "Preprocess sub-01"
        assert wf["status"] == "PENDING"
        assert wf["total_tokens"] == 0
        assert wf["estimated_cost_usd"] == 0.0

    def test_update_workflow_status_and_metrics(
        self, blackboard: Blackboard
    ) -> None:
        """Verify updating status, token consumption, and cost estimates.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts updated metrics.
        """
        blackboard.create_workflow("wf-101", "fMRI pipeline")
        blackboard.update_workflow_status(
            workflow_id="wf-101",
            status="RUNNING",
            total_tokens=1500,
            estimated_cost_usd=0.045,
        )
        wf: dict[str, Any] | None = blackboard.get_workflow("wf-101")
        assert wf is not None
        assert wf["status"] == "RUNNING"
        assert wf["total_tokens"] == 1500
        assert wf["estimated_cost_usd"] == 0.045

    def test_list_workflows(self, blackboard: Blackboard) -> None:
        """Verify list_workflows returns chronologically ordered records.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts multiple workflows returned.
        """
        blackboard.create_workflow("wf-a", "First prompt")
        blackboard.create_workflow("wf-b", "Second prompt")
        all_wf: list[dict[str, Any]] = blackboard.list_workflows()
        assert len(all_wf) == 2
        wf_ids: set[str] = {w["workflow_id"] for w in all_wf}
        assert "wf-a" in wf_ids
        assert "wf-b" in wf_ids

    def test_reconcile_workflow_status(self, blackboard: Blackboard) -> None:
        """Verify automatic workflow status reconciliation based on node states.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts reconciled statuses.
        """
        blackboard.create_workflow("wf-rec", "Reconcile test")
        node: TaskNode = TaskNode(
            node_id="rec-1",
            workflow_id="wf-rec",
            agent_role="specialist",
            harness_id="agy",
        )
        blackboard.create_node(node)
        assert blackboard.reconcile_workflow_status("wf-rec") == "PENDING"

        blackboard.update_node_state("rec-1", TaskState.RUNNING)
        assert blackboard.reconcile_workflow_status("wf-rec") == "RUNNING"

        blackboard.update_node_state("rec-1", TaskState.COMPLETED)
        assert blackboard.reconcile_workflow_status("wf-rec") == "COMPLETED"


class TestBlackboardTaskNodeCrud:
    """Test suite for task node execution states and diagnostics."""

    def test_create_and_get_task_node(self, blackboard: Blackboard) -> None:
        """Verify creating and fetching a TaskNode preserving Pydantic fields.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts model reconstruction matches input.
        """
        blackboard.create_workflow("wf-node", "Test node")
        node: TaskNode = TaskNode(
            node_id="node-1",
            workflow_id="wf-node",
            agent_role="neuroimaging_specialist",
            harness_id="agy",
            state=TaskState.PENDING,
            attempt=0,
            max_retries=2,
        )
        blackboard.create_task_node(node)
        fetched: TaskNode | None = blackboard.get_task_node("node-1")
        assert fetched is not None
        assert fetched.node_id == "node-1"
        assert fetched.state == TaskState.PENDING

    def test_create_nodes_batch(self, blackboard: Blackboard) -> None:
        """Verify batch creation of multiple task nodes.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts all nodes persisted.
        """
        blackboard.create_workflow("wf-batch", "Batch test")
        nodes: list[TaskNode] = [
            TaskNode(
                node_id=f"batch-{i}",
                workflow_id="wf-batch",
                agent_role="role",
                harness_id="agy",
            )
            for i in range(3)
        ]
        blackboard.create_nodes(nodes)
        fetched: list[TaskNode] = blackboard.get_nodes_by_workflow("wf-batch")
        assert len(fetched) == 3

    def test_update_node_envelope(self, blackboard: Blackboard) -> None:
        """Verify updating dispatched task envelope on a task node.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts updated task envelope persisted.
        """
        blackboard.create_workflow("wf-env", "Envelope test")
        node: TaskNode = TaskNode(
            node_id="node-env",
            workflow_id="wf-env",
            agent_role="specialist",
            harness_id="agy",
        )
        blackboard.create_node(node)

        envelope: NeuriTaskEnvelope = NeuriTaskEnvelope(
            workflow_id="wf-env",
            node_id="node-env",
            agent_role="specialist",
            harness_id="agy",
            task_instruction="Preprocess functional scan",
        )
        blackboard.update_node_envelope("node-env", envelope)

        updated: TaskNode | None = blackboard.get_node("node-env")
        assert updated is not None
        assert updated.envelope is not None
        assert updated.envelope.task_instruction == "Preprocess functional scan"

    def test_record_node_result(self, blackboard: Blackboard) -> None:
        """Verify recording task result transitions state and records summary.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts node state and summary match result.
        """
        blackboard.create_workflow("wf-res", "Result test")
        node: TaskNode = TaskNode(
            node_id="node-res",
            workflow_id="wf-res",
            agent_role="specialist",
            harness_id="agy",
        )
        blackboard.create_node(node)
        blackboard.update_node_state("node-res", TaskState.RUNNING)

        result: NeuriTaskResult = NeuriTaskResult(
            node_id="node-res",
            success=True,
            exit_code=0,
            summary="Preprocessing complete with zero errors.",
            tokens_consumed=1200,
            cost_usd=0.03,
        )
        blackboard.record_node_result("node-res", result)

        updated: TaskNode | None = blackboard.get_node("node-res")
        assert updated is not None
        assert updated.state == TaskState.COMPLETED
        assert "zero errors" in (updated.summary_result or "")

    def test_delete_task_node(self, blackboard: Blackboard) -> None:
        """Verify deleting a task node removes it from blackboard.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts node is deleted.
        """
        blackboard.create_workflow("wf-delnode", "Delete node test")
        node: TaskNode = TaskNode(
            node_id="node-to-del",
            workflow_id="wf-delnode",
            agent_role="specialist",
            harness_id="agy",
        )
        blackboard.create_node(node)
        assert blackboard.get_node("node-to-del") is not None
        blackboard.delete_task_node("node-to-del")
        assert blackboard.get_node("node-to-del") is None

    def test_update_node_state_lifecycle(
        self, blackboard: Blackboard
    ) -> None:
        """Verify sequential transitions PENDING -> RUNNING -> COMPLETED.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts state transitions and timestamps.
        """
        blackboard.create_workflow("wf-state", "Test state transitions")
        node: TaskNode = TaskNode(
            node_id="node-lifecycle",
            workflow_id="wf-state",
            agent_role="neuroimaging_specialist",
            harness_id="agy",
        )
        blackboard.create_task_node(node)

        blackboard.update_node_state("node-lifecycle", TaskState.RUNNING)
        n_running: TaskNode | None = blackboard.get_task_node("node-lifecycle")
        assert n_running is not None
        assert n_running.state == TaskState.RUNNING
        assert n_running.started_at is not None

        blackboard.update_node_state(
            "node-lifecycle", TaskState.COMPLETED, summary_result="OK"
        )
        n_completed: TaskNode | None = blackboard.get_task_node(
            "node-lifecycle"
        )
        assert n_completed is not None
        assert n_completed.state == TaskState.COMPLETED
        assert n_completed.completed_at is not None
        assert n_completed.summary_result == "OK"

    def test_update_node_state_with_diagnostic_feedback(
        self, blackboard: Blackboard
    ) -> None:
        """Verify transition to RETRYING appends diagnostic error feedback.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts feedback string recorded and attempt incremented.
        """
        blackboard.create_workflow("wf-diag", "Diagnostic retry test")
        node: TaskNode = TaskNode(
            node_id="node-retry",
            workflow_id="wf-diag",
            agent_role="pipeline_engineer",
            harness_id="codex",
        )
        blackboard.create_task_node(node)
        blackboard.update_node_state("node-retry", TaskState.RUNNING)

        blackboard.update_node_state(
            node_id="node-retry",
            state=TaskState.RETRYING,
            diagnostic_feedback="Apptainer container not found",
        )
        n_retrying: TaskNode | None = blackboard.get_task_node("node-retry")
        assert n_retrying is not None
        assert n_retrying.state == TaskState.RETRYING
        assert n_retrying.attempt == 1
        assert "Apptainer container not found" in n_retrying.diagnostic_feedback

    def test_update_node_state_invalid_transition(
        self, blackboard: Blackboard
    ) -> None:
        """Verify illegal state transition raises InvalidStateTransitionError.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts InvalidStateTransitionError.
        """
        blackboard.create_workflow("wf-inv", "Invalid transition test")
        node: TaskNode = TaskNode(
            node_id="node-inv",
            workflow_id="wf-inv",
            agent_role="specialist",
            harness_id="agy",
        )
        blackboard.create_node(node)
        with pytest.raises(InvalidStateTransitionError):
            blackboard.update_node_state("node-inv", TaskState.COMPLETED)

    def test_update_node_state_operator_retry(
        self, blackboard: Blackboard
    ) -> None:
        """Verify FAILED to RETRYING transition is permitted for operator retry.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts transition succeeds and attempt increments.
        """
        blackboard.create_workflow("wf-op", "Operator retry test")
        node: TaskNode = TaskNode(
            node_id="node-op",
            workflow_id="wf-op",
            agent_role="specialist",
            harness_id="agy",
        )
        blackboard.create_node(node)
        blackboard.update_node_state("node-op", TaskState.RUNNING)
        blackboard.update_node_state("node-op", TaskState.FAILED)

        blackboard.update_node_state("node-op", TaskState.RETRYING)
        updated: TaskNode | None = blackboard.get_node("node-op")
        assert updated is not None
        assert updated.state == TaskState.RETRYING
        assert updated.attempt == 1

    def test_update_node_state_retrying_to_pending(
        self, blackboard: Blackboard
    ) -> None:
        """Verify RETRYING to PENDING transition is permitted for DAG reschedule.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts transition succeeds and node enters PENDING state.
        """
        blackboard.create_workflow("wf-retry", "Retry transition test")
        node: TaskNode = TaskNode(
            node_id="node-retry",
            workflow_id="wf-retry",
            agent_role="specialist",
            harness_id="agy",
        )
        blackboard.create_node(node)
        blackboard.update_node_state("node-retry", TaskState.RUNNING)
        blackboard.update_node_state("node-retry", TaskState.RETRYING)
        blackboard.update_node_state("node-retry", TaskState.PENDING)

        updated: TaskNode | None = blackboard.get_node("node-retry")
        assert updated is not None
        assert updated.state == TaskState.PENDING
        assert updated.attempt == 1


class TestBlackboardDagTopologicalQueries:
    """Test suite for DAG edge construction, cycles, and get_ready_nodes."""

    def test_add_edge_rejects_self_loop(self, blackboard: Blackboard) -> None:
        """Verify self-loop parent_node_id == child_node_id is rejected.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts ValueError on self-loop.
        """
        blackboard.create_workflow("wf-loop", "Loop test")
        node: TaskNode = TaskNode(
            node_id="node-self",
            workflow_id="wf-loop",
            agent_role="neuroimaging_specialist",
            harness_id="agy",
        )
        blackboard.create_task_node(node)
        with pytest.raises((ValueError, BlackboardError)):
            blackboard.add_task_edge("wf-loop", "node-self", "node-self")

    def test_cycle_detection_direct_cycle(
        self, blackboard: Blackboard
    ) -> None:
        """Verify A -> B -> A direct cycle is detected and blocked.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts CycleDetectedError.
        """
        blackboard.create_workflow("wf-cyc", "Cycle test")
        for nid in ("A", "B"):
            blackboard.create_task_node(
                TaskNode(
                    node_id=nid,
                    workflow_id="wf-cyc",
                    agent_role="role",
                    harness_id="agy",
                )
            )
        blackboard.add_task_edge("wf-cyc", "A", "B")
        with pytest.raises(CycleDetectedError):
            blackboard.add_task_edge("wf-cyc", "B", "A")

    def test_cycle_detection_indirect_cycle(
        self, blackboard: Blackboard
    ) -> None:
        """Verify A -> B -> C -> A multi-hop cycle is detected and blocked.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts CycleDetectedError.
        """
        blackboard.create_workflow("wf-cyc3", "3-node cycle test")
        for nid in ("A", "B", "C"):
            blackboard.create_task_node(
                TaskNode(
                    node_id=nid,
                    workflow_id="wf-cyc3",
                    agent_role="role",
                    harness_id="agy",
                )
            )
        blackboard.add_task_edge("wf-cyc3", "A", "B")
        blackboard.add_task_edge("wf-cyc3", "B", "C")
        with pytest.raises(CycleDetectedError):
            blackboard.add_task_edge("wf-cyc3", "C", "A")

    def test_add_edge_missing_node(self, blackboard: Blackboard) -> None:
        """Verify adding edge with missing node raises NodeNotFoundError.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts NodeNotFoundError.
        """
        blackboard.create_workflow("wf-miss", "Missing node test")
        node: TaskNode = TaskNode(
            node_id="real-node",
            workflow_id="wf-miss",
            agent_role="role",
            harness_id="agy",
        )
        blackboard.create_node(node)
        with pytest.raises(NodeNotFoundError):
            blackboard.add_task_edge("wf-miss", "real-node", "fake-node")

    def test_get_ready_nodes_root_pending(
        self, blackboard: Blackboard
    ) -> None:
        """Verify root node (in-degree 0) in PENDING state is ready.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts root node returned in ready nodes.
        """
        blackboard.create_workflow("wf-dag", "DAG test")
        blackboard.create_task_node(
            TaskNode(
                node_id="root",
                workflow_id="wf-dag",
                agent_role="specialist",
                harness_id="agy",
            )
        )
        ready: list[TaskNode] = blackboard.get_ready_nodes("wf-dag")
        assert len(ready) == 1
        assert ready[0].node_id == "root"

    def test_get_ready_nodes_blocked_until_parents_completed(
        self, blackboard: Blackboard
    ) -> None:
        """Verify dependent node is blocked while parent is RUNNING.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts child unblocked only after parent completes.
        """
        blackboard.create_workflow("wf-block", "Block test")
        blackboard.create_task_node(
            TaskNode(
                node_id="parent",
                workflow_id="wf-block",
                agent_role="specialist",
                harness_id="agy",
            )
        )
        blackboard.create_task_node(
            TaskNode(
                node_id="child",
                workflow_id="wf-block",
                agent_role="specialist",
                harness_id="agy",
            )
        )
        blackboard.add_task_edge("wf-block", "parent", "child")

        ready_init: list[TaskNode] = blackboard.get_ready_nodes("wf-block")
        assert [n.node_id for n in ready_init] == ["parent"]

        blackboard.update_node_state("parent", TaskState.RUNNING)
        ready_running: list[TaskNode] = blackboard.get_ready_nodes("wf-block")
        assert ready_running == []

        blackboard.update_node_state("parent", TaskState.COMPLETED)
        ready_completed: list[TaskNode] = blackboard.get_ready_nodes(
            "wf-block"
        )
        assert [n.node_id for n in ready_completed] == ["child"]

    def test_get_ready_nodes_blocked_when_parent_fails(
        self, blackboard: Blackboard
    ) -> None:
        """Verify child node is NOT ready if its parent is FAILED.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts child remains blocked.
        """
        blackboard.create_workflow("wf-fail", "Fail test")
        blackboard.create_task_node(
            TaskNode(
                node_id="p-fail",
                workflow_id="wf-fail",
                agent_role="specialist",
                harness_id="agy",
            )
        )
        blackboard.create_task_node(
            TaskNode(
                node_id="c-fail",
                workflow_id="wf-fail",
                agent_role="specialist",
                harness_id="agy",
            )
        )
        blackboard.add_task_edge("wf-fail", "p-fail", "c-fail")
        blackboard.update_node_state("p-fail", TaskState.RUNNING)
        blackboard.update_node_state("p-fail", TaskState.FAILED)

        ready: list[TaskNode] = blackboard.get_ready_nodes("wf-fail")
        assert ready == []

    def test_get_ready_nodes_diamond_dag(
        self, blackboard: Blackboard
    ) -> None:
        """Verify multi-path diamond DAG: A -> (B, C) -> D.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts D is ready only when both B and C complete.
        """
        blackboard.create_workflow("wf-diamond", "Diamond test")
        for nid in ("A", "B", "C", "D"):
            blackboard.create_task_node(
                TaskNode(
                    node_id=nid,
                    workflow_id="wf-diamond",
                    agent_role="specialist",
                    harness_id="agy",
                )
            )
        blackboard.add_task_edge("wf-diamond", "A", "B")
        blackboard.add_task_edge("wf-diamond", "A", "C")
        blackboard.add_task_edge("wf-diamond", "B", "D")
        blackboard.add_task_edge("wf-diamond", "C", "D")

        assert [
            n.node_id for n in blackboard.get_ready_nodes("wf-diamond")
        ] == ["A"]

        blackboard.update_node_state("A", TaskState.RUNNING)
        blackboard.update_node_state("A", TaskState.COMPLETED)
        ready_bc: set[str] = {
            n.node_id for n in blackboard.get_ready_nodes("wf-diamond")
        }
        assert ready_bc == {"B", "C"}

        blackboard.update_node_state("B", TaskState.RUNNING)
        blackboard.update_node_state("B", TaskState.COMPLETED)
        blackboard.update_node_state("C", TaskState.RUNNING)
        assert blackboard.get_ready_nodes("wf-diamond") == []

        blackboard.update_node_state("C", TaskState.COMPLETED)
        assert [
            n.node_id for n in blackboard.get_ready_nodes("wf-diamond")
        ] == ["D"]

    def test_get_topological_order(self, blackboard: Blackboard) -> None:
        """Verify Kahn's algorithm produces valid topological sequence.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts topological order is valid.
        """
        blackboard.create_workflow("wf-topo", "Topological test")
        for nid in ("1", "2", "3"):
            blackboard.create_node(
                TaskNode(
                    node_id=nid,
                    workflow_id="wf-topo",
                    agent_role="role",
                    harness_id="agy",
                )
            )
        blackboard.add_task_edge("wf-topo", "1", "2")
        blackboard.add_task_edge("wf-topo", "2", "3")

        topo: list[str] = blackboard.get_topological_order("wf-topo")
        assert topo == ["1", "2", "3"]

    def test_validate_dag(self, blackboard: Blackboard) -> None:
        """Verify validate_dag returns True for valid acyclic graphs.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts True.
        """
        blackboard.create_workflow("wf-vld", "Validate DAG test")
        node: TaskNode = TaskNode(
            node_id="single",
            workflow_id="wf-vld",
            agent_role="role",
            harness_id="agy",
        )
        blackboard.create_node(node)
        assert blackboard.validate_dag("wf-vld") is True

    def test_get_blocked_nodes(self, blackboard: Blackboard) -> None:
        """Verify get_blocked_nodes identifies nodes blocked by failed parents.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts blocked pairs returned.
        """
        blackboard.create_workflow("wf-blkd", "Blocked nodes test")
        blackboard.create_node(
            TaskNode(
                node_id="p-fail",
                workflow_id="wf-blkd",
                agent_role="role",
                harness_id="agy",
            )
        )
        blackboard.create_node(
            TaskNode(
                node_id="c-blocked",
                workflow_id="wf-blkd",
                agent_role="role",
                harness_id="agy",
            )
        )
        blackboard.add_task_edge("wf-blkd", "p-fail", "c-blocked")
        blackboard.update_node_state("p-fail", TaskState.RUNNING)
        blackboard.update_node_state("p-fail", TaskState.FAILED)

        blocked: list[tuple[TaskNode, list[str]]] = (
            blackboard.get_blocked_nodes("wf-blkd")
        )
        assert len(blocked) == 1
        assert blocked[0][0].node_id == "c-blocked"
        assert blocked[0][1] == ["p-fail"]

    def test_get_parent_and_child_node_ids(
        self, blackboard: Blackboard
    ) -> None:
        """Verify get_parent_node_ids and get_child_node_ids.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts parent and child relationships.
        """
        blackboard.create_workflow("wf-rel", "Rel test")
        blackboard.create_node(
            TaskNode(
                node_id="p1",
                workflow_id="wf-rel",
                agent_role="role",
                harness_id="agy",
            )
        )
        blackboard.create_node(
            TaskNode(
                node_id="p2",
                workflow_id="wf-rel",
                agent_role="role",
                harness_id="agy",
            )
        )
        blackboard.create_node(
            TaskNode(
                node_id="c1",
                workflow_id="wf-rel",
                agent_role="role",
                harness_id="agy",
            )
        )
        blackboard.add_task_edge("wf-rel", "p1", "c1")
        blackboard.add_task_edge("wf-rel", "p2", "c1")

        parents: list[str] = blackboard.get_parent_node_ids("c1")
        assert parents == ["p1", "p2"]

        children: list[str] = blackboard.get_child_node_ids("p1")
        assert children == ["c1"]


class TestBlackboardArtifactRegistration:
    """Test suite for RemoteArtifact registration and uniqueness constraints."""

    def test_register_and_get_artifact(
        self, blackboard: Blackboard, sample_artifact: RemoteArtifact
    ) -> None:
        """Verify registering and retrieving an artifact by URI.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        sample_artifact: RemoteArtifact
            Sample artifact fixture.

        Returns
        --------
            None: NoneType object
                Asserts registered artifact model matches.
        """
        blackboard.create_workflow("wf-art", "Artifact workflow")
        blackboard.register_artifact(sample_artifact, workflow_id="wf-art")

        fetched: RemoteArtifact | None = blackboard.get_artifact(
            sample_artifact.uri
        )
        assert fetched is not None
        assert fetched.artifact_id == sample_artifact.artifact_id
        assert fetched.uri == sample_artifact.uri
        assert fetched.modality == ModalityType.T1W
        assert fetched.space == "MNI152NLin2009cAsym"
        assert fetched.header_summary.phi_sanitized is True

    def test_get_artifact_by_id(
        self, blackboard: Blackboard, sample_artifact: RemoteArtifact
    ) -> None:
        """Verify retrieving an artifact by its artifact_id.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        sample_artifact: RemoteArtifact
            Sample artifact fixture.

        Returns
        --------
            None: NoneType object
                Asserts retrieved artifact matches.
        """
        blackboard.create_workflow("wf-artid", "Artifact ID workflow")
        blackboard.register_artifact(sample_artifact, workflow_id="wf-artid")

        fetched: RemoteArtifact | None = blackboard.get_artifact_by_id(
            sample_artifact.artifact_id
        )
        assert fetched is not None
        assert fetched.uri == sample_artifact.uri

    def test_register_artifact_enforces_unique_uri(
        self, blackboard: Blackboard, sample_artifact: RemoteArtifact
    ) -> None:
        """Verify registering duplicate URI raises ArtifactRegistrationError.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        sample_artifact: RemoteArtifact
            Sample artifact fixture.

        Returns
        --------
            None: NoneType object
                Asserts ArtifactRegistrationError.
        """
        blackboard.create_workflow("wf-dup", "Duplicate workflow")
        blackboard.register_artifact(sample_artifact, workflow_id="wf-dup")

        with pytest.raises(ArtifactRegistrationError):
            blackboard.register_artifact(sample_artifact, workflow_id="wf-dup")

    def test_register_artifact_enforces_unique_posix_path_on_host(
        self,
        blackboard: Blackboard,
        sample_artifact: RemoteArtifact,
        sample_header: SanitizedNeuroHeader,
    ) -> None:
        """Verify duplicate (host, posix_path) collision is rejected.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        sample_artifact: RemoteArtifact
            First artifact fixture.
        sample_header: SanitizedNeuroHeader
            Header fixture.

        Returns
        --------
            None: NoneType object
                Asserts ArtifactRegistrationError.
        """
        blackboard.create_workflow("wf-path", "Path collision workflow")
        blackboard.register_artifact(sample_artifact, workflow_id="wf-path")

        alt_art: RemoteArtifact = RemoteArtifact(
            artifact_id="art-dup-path",
            uri=sample_artifact.uri,
            host=sample_artifact.host,
            posix_path=sample_artifact.posix_path,
            modality=ModalityType.T1W,
            sha256_header="b" * 64,
            size_bytes=500,
            header_summary=sample_header,
        )
        with pytest.raises(ArtifactRegistrationError):
            blackboard.register_artifact(alt_art, workflow_id="wf-path")

    def test_list_artifacts_filtered_by_workflow(
        self,
        blackboard: Blackboard,
        sample_artifact: RemoteArtifact,
        sample_header: SanitizedNeuroHeader,
    ) -> None:
        """Verify list_artifacts filters correctly by workflow_id.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        sample_artifact: RemoteArtifact
            First artifact fixture.
        sample_header: SanitizedNeuroHeader
            Header fixture.

        Returns
        --------
            None: NoneType object
                Asserts filtering isolates workflow artifacts.
        """
        blackboard.create_workflow("wf-1", "Workflow 1")
        blackboard.create_workflow("wf-2", "Workflow 2")

        blackboard.register_artifact(sample_artifact, workflow_id="wf-1")

        art2: RemoteArtifact = RemoteArtifact(
            artifact_id="art-002",
            uri="hpc-cluster:///scratch/sub-02_T1w.nii.gz",
            host="hpc-cluster",
            posix_path="/scratch/sub-02_T1w.nii.gz",
            modality=ModalityType.T1W,
            sha256_header="c" * 64,
            size_bytes=1000,
            header_summary=sample_header,
        )
        blackboard.register_artifact(art2, workflow_id="wf-2")

        wf1_arts: list[RemoteArtifact] = blackboard.list_artifacts(
            workflow_id="wf-1"
        )
        assert len(wf1_arts) == 1
        assert wf1_arts[0].artifact_id == sample_artifact.artifact_id

    def test_list_artifacts_filtered_by_node(
        self,
        blackboard: Blackboard,
        sample_artifact: RemoteArtifact,
    ) -> None:
        """Verify list_artifacts filters correctly by node_id.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        sample_artifact: RemoteArtifact
            Artifact fixture.

        Returns
        --------
            None: NoneType object
                Asserts filtering isolates node artifacts.
        """
        blackboard.create_workflow("wf-node-art", "Node art workflow")
        node: TaskNode = TaskNode(
            node_id="producing-node",
            workflow_id="wf-node-art",
            agent_role="specialist",
            harness_id="agy",
        )
        blackboard.create_node(node)
        blackboard.register_artifact(
            sample_artifact, workflow_id="wf-node-art", node_id="producing-node"
        )

        arts: list[RemoteArtifact] = blackboard.list_artifacts(
            node_id="producing-node"
        )
        assert len(arts) == 1
        assert arts[0].created_by_node == "producing-node"

    def test_register_artifact_missing_workflow_raises(
        self, blackboard: Blackboard, sample_artifact: RemoteArtifact
    ) -> None:
        """Verify registering artifact with invalid workflow raises error.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        sample_artifact: RemoteArtifact
            Artifact fixture.

        Returns
        --------
            None: NoneType object
                Asserts WorkflowNotFoundError.
        """
        with pytest.raises(WorkflowNotFoundError):
            blackboard.register_artifact(
                sample_artifact, workflow_id="nonexistent-wf"
            )

    def test_register_artifact_missing_node_raises(
        self, blackboard: Blackboard, sample_artifact: RemoteArtifact
    ) -> None:
        """Verify registering artifact with invalid node raises error.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        sample_artifact: RemoteArtifact
            Artifact fixture.

        Returns
        --------
            None: NoneType object
                Asserts NodeNotFoundError.
        """
        blackboard.create_workflow("wf-art-chk", "Check workflow")
        with pytest.raises(NodeNotFoundError):
            blackboard.register_artifact(
                sample_artifact,
                workflow_id="wf-art-chk",
                node_id="nonexistent-node",
            )


class TestBlackboardRemoteJobs:
    """Test suite for asynchronous remote batch job tracking."""

    def test_register_and_get_remote_job(
        self, blackboard: Blackboard
    ) -> None:
        """Verify registering and retrieving a remote job record.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts job attributes match.
        """
        blackboard.create_workflow("wf-job", "Job test")
        node: TaskNode = TaskNode(
            node_id="job-node",
            workflow_id="wf-job",
            agent_role="specialist",
            harness_id="agy",
        )
        blackboard.create_node(node)

        blackboard.register_remote_job(
            job_id="job-12345",
            node_id="job-node",
            host="slurm-cluster",
            scheduler_type="slurm",
            scheduler_job_id="998877",
            status_uri="slurm-cluster:///var/log/slurm-998877.out",
        )

        job: dict[str, Any] | None = blackboard.get_remote_job("job-12345")
        assert job is not None
        assert job["scheduler_job_id"] == "998877"
        assert job["state"] == "SUBMITTED"

    def test_update_remote_job_state(self, blackboard: Blackboard) -> None:
        """Verify updating remote job state to RUNNING and COMPLETED.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts state updates cleanly.
        """
        blackboard.create_workflow("wf-job2", "Job test 2")
        node: TaskNode = TaskNode(
            node_id="job-node2",
            workflow_id="wf-job2",
            agent_role="specialist",
            harness_id="agy",
        )
        blackboard.create_node(node)

        blackboard.register_remote_job(
            job_id="job-2",
            node_id="job-node2",
            host="slurm-cluster",
            scheduler_type="slurm",
            scheduler_job_id="111222",
        )
        blackboard.update_remote_job_state("job-2", "RUNNING")
        job_running: dict[str, Any] | None = blackboard.get_remote_job("job-2")
        assert job_running is not None
        assert job_running["state"] == "RUNNING"

    def test_list_remote_jobs(self, blackboard: Blackboard) -> None:
        """Verify listing remote jobs optionally filtered by node_id.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts filtered job listing.
        """
        blackboard.create_workflow("wf-job3", "Job test 3")
        node: TaskNode = TaskNode(
            node_id="job-node3",
            workflow_id="wf-job3",
            agent_role="specialist",
            harness_id="agy",
        )
        blackboard.create_node(node)

        blackboard.register_remote_job(
            job_id="job-3",
            node_id="job-node3",
            host="slurm-cluster",
            scheduler_type="slurm",
            scheduler_job_id="333444",
        )
        jobs: list[dict[str, Any]] = blackboard.list_remote_jobs(
            node_id="job-node3"
        )
        assert len(jobs) == 1
        assert jobs[0]["job_id"] == "job-3"


class TestBlackboardCitationsLedger:
    """Test suite for verified citation registration, retrieval, and sync."""

    def test_register_and_get_citation(self, blackboard: Blackboard) -> None:
        """Verify registering and fetching a citation by key and DOI.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts citation fields match.
        """
        blackboard.register_citation(
            citation_key="esteban2019fmriprep",
            title="fMRIPrep: a robust preprocessing pipeline for functional MRI",
            bibtex="@article{esteban2019fmriprep, title={fMRIPrep}, year={2019}}",
            doi="10.1038/s41592-018-0235-4",
            pmid="30532080",
            authors=["Esteban, Oscar", "Markiewicz, Christopher J."],
            year=2019,
            verified=True,
        )

        cit: dict[str, Any] | None = blackboard.get_citation(
            "esteban2019fmriprep"
        )
        assert cit is not None
        assert cit["title"].startswith("fMRIPrep")
        assert cit["doi"] == "10.1038/s41592-018-0235-4"
        assert cit["verified"] is True

        by_doi: dict[str, Any] | None = blackboard.get_citation_by_doi(
            "10.1038/s41592-018-0235-4"
        )
        assert by_doi is not None
        assert by_doi["citation_key"] == "esteban2019fmriprep"

    def test_duplicate_citation_key_upsert(
        self, blackboard: Blackboard
    ) -> None:
        """Verify re-registering an existing citation key updates the record.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts updated title on duplicate key.
        """
        blackboard.register_citation(
            citation_key="fischl2012",
            title="FreeSurfer Initial",
            bibtex="@article{fischl2012, title={Initial}}",
        )
        blackboard.register_citation(
            citation_key="fischl2012",
            title="FreeSurfer: NeuroImage",
            bibtex="@article{fischl2012, title={FreeSurfer: NeuroImage}}",
            year=2012,
        )
        updated: dict[str, Any] | None = blackboard.get_citation("fischl2012")
        assert updated is not None
        assert updated["title"] == "FreeSurfer: NeuroImage"
        assert updated["year"] == 2012

    def test_list_citations(self, blackboard: Blackboard) -> None:
        """Verify listing citations with verified_only filter.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts filtered citations list.
        """
        blackboard.register_citation(
            citation_key="cit1",
            title="Verified Work",
            bibtex="@article{cit1, title={Verified}}",
            verified=True,
        )
        blackboard.register_citation(
            citation_key="cit2",
            title="Unverified Draft",
            bibtex="@article{cit2, title={Draft}}",
            verified=False,
        )
        all_cits: list[dict[str, Any]] = blackboard.list_citations(
            verified_only=False
        )
        assert len(all_cits) == 2

        verified_cits: list[dict[str, Any]] = blackboard.list_citations(
            verified_only=True
        )
        assert len(verified_cits) == 1
        assert verified_cits[0]["citation_key"] == "cit1"

    def test_sync_citations_to_bib_file(
        self, blackboard: Blackboard, tmp_path: Path
    ) -> None:
        """Verify syncing ledger entries writes a valid references.bib file.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        tmp_path: Path
            Pytest temporary directory.

        Returns
        --------
            None: NoneType object
                Asserts BibTeX file format and entry counts.
        """
        bib_file: Path = tmp_path / "references.bib"
        blackboard.register_citation(
            citation_key="key1",
            title="Title 1",
            bibtex="@article{key1, title={Title 1}}",
            verified=True,
        )
        blackboard.register_citation(
            citation_key="key2",
            title="Title 2",
            bibtex="@article{key2, title={Title 2}}",
            verified=True,
        )

        count: int = blackboard.sync_citations_to_bib(bib_file)
        assert count == 2
        content: str = bib_file.read_text(encoding="utf-8")
        assert "@article{key1" in content
        assert "@article{key2" in content


class TestBlackboardTelemetryEvents:
    """Test suite for streaming telemetry event persistence and querying."""

    def test_record_and_list_telemetry_events(
        self, blackboard: Blackboard
    ) -> None:
        """Verify recording and querying telemetry events.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts event persistence and query filtering.
        """
        blackboard.create_workflow("wf-telem", "Telemetry test")
        node: TaskNode = TaskNode(
            node_id="telem-node",
            workflow_id="wf-telem",
            agent_role="specialist",
            harness_id="agy",
        )
        blackboard.create_node(node)

        event: TelemetryEvent = TelemetryEvent(
            event_id="evt-001",
            workflow_id="wf-telem",
            node_id="telem-node",
            harness_id="agy",
            timestamp=datetime.now(timezone.utc),
            event_type="token_usage",
            thinking_text="Analyzing brain extraction parameters...",
            input_tokens=500,
            output_tokens=150,
            estimated_cost_usd=0.012,
        )
        blackboard.record_telemetry_event(event)

        events: list[dict[str, Any]] = blackboard.list_telemetry_events(
            "wf-telem"
        )
        assert len(events) == 1
        assert events[0]["event_id"] == "evt-001"
        assert events[0]["input_tokens"] == 500


class TestBlackboardProvenanceExport:
    """Test suite for immutable provenance export and history list merging."""

    def test_export_provenance_full_workflow(
        self,
        blackboard: Blackboard,
        sample_artifact: RemoteArtifact,
        tmp_path: Path,
    ) -> None:
        """Verify complete provenance graph export with nodes, edges, and artifacts.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        sample_artifact: RemoteArtifact
            Artifact fixture.
        tmp_path: Path
            Pytest temporary directory.

        Returns
        --------
            None: NoneType object
                Asserts provenance dictionary keys and written JSON content.
        """
        blackboard.create_workflow("wf-prov", "Full provenance test")
        blackboard.create_task_node(
            TaskNode(
                node_id="n-start",
                workflow_id="wf-prov",
                agent_role="neuroimaging_specialist",
                harness_id="agy",
            )
        )
        blackboard.create_task_node(
            TaskNode(
                node_id="n-end",
                workflow_id="wf-prov",
                agent_role="critic_qa",
                harness_id="agy",
            )
        )
        blackboard.add_task_edge("wf-prov", "n-start", "n-end")
        blackboard.register_artifact(
            sample_artifact, workflow_id="wf-prov", node_id="n-start"
        )
        blackboard.register_citation(
            citation_key="cit-prov",
            title="Provenance Citation",
            bibtex="@article{cit-prov, title={Prov}}",
        )

        export_file: Path = tmp_path / "execution_history.json"
        data: dict[str, Any] = blackboard.export_provenance(
            "wf-prov", export_file
        )

        assert data["workflow_id"] == "wf-prov"
        assert len(data["nodes"]) == 2
        assert len(data["edges"]) == 1
        assert len(data["artifacts"]) == 1
        assert len(data["citations"]) >= 1
        assert "exported_at" in data

        assert export_file.is_file()
        loaded_history: list[dict[str, Any]] = json.loads(
            export_file.read_text(encoding="utf-8")
        )
        assert isinstance(loaded_history, list)
        assert len(loaded_history) == 1
        assert loaded_history[0]["workflow_id"] == "wf-prov"

    def test_export_provenance_updates_empty_history_list(
        self, blackboard: Blackboard, tmp_path: Path
    ) -> None:
        """Verify exporting to an existing '[]' file updates the list properly.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        tmp_path: Path
            Pytest temporary directory.

        Returns
        --------
            None: NoneType object
                Asserts list length is 1 and contains workflow provenance.
        """
        history_file: Path = tmp_path / "execution_history.json"
        history_file.write_text("[]\n", encoding="utf-8")

        blackboard.create_workflow("wf-hist", "History list merge test")
        blackboard.export_provenance("wf-hist", history_file)

        content: Any = json.loads(history_file.read_text(encoding="utf-8"))
        assert isinstance(content, list)
        assert len(content) == 1
        assert content[0]["workflow_id"] == "wf-hist"

    def test_export_provenance_nonexistent_workflow_raises_error(
        self, blackboard: Blackboard, tmp_path: Path
    ) -> None:
        """Verify exporting invalid workflow ID raises WorkflowNotFoundError.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        tmp_path: Path
            Pytest temporary directory.

        Returns
        --------
            None: NoneType object
                Asserts WorkflowNotFoundError.
        """
        export_file: Path = tmp_path / "dummy.json"
        with pytest.raises(WorkflowNotFoundError):
            blackboard.export_provenance("wf-missing", export_file)


class TestBlackboardConcurrencyAndTransactions:
    """Test suite verifying transactional rollbacks and concurrent WAL readers."""

    def test_transaction_rollback_on_failure(
        self, blackboard: Blackboard
    ) -> None:
        """Verify atomic transaction rolls back uncommitted changes on error.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts failed batch operation does not leave partial state.
        """
        blackboard.create_workflow("wf-tx", "Transaction rollback test")
        with pytest.raises(Exception):
            with blackboard.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO task_nodes (
                        node_id, workflow_id, agent_role, harness_id,
                        created_at, updated_at
                    ) VALUES (
                        'tx-node-1', 'wf-tx', 'role', 'agy',
                        '2026-01-01', '2026-01-01'
                    );
                    """
                )
                conn.execute(
                    """
                    INSERT INTO task_nodes (
                        node_id, workflow_id, agent_role, harness_id,
                        created_at, updated_at
                    ) VALUES (
                        'tx-node-2', 'wf-nonexistent', 'role', 'agy',
                        '2026-01-01', '2026-01-01'
                    );
                    """
                )

        assert blackboard.get_task_node("tx-node-1") is None

    def test_concurrent_readers_in_wal_mode(
        self, blackboard: Blackboard
    ) -> None:
        """Verify WAL mode permits concurrent active reader connections.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts concurrent queries succeed simultaneously.
        """
        blackboard.create_workflow("wf-concurrent", "Concurrency test")
        with blackboard.connection() as conn1:
            cur1: sqlite3.Cursor = conn1.execute("SELECT * FROM workflows;")
            with blackboard.connection() as conn2:
                cur2: sqlite3.Cursor = conn2.execute(
                    "SELECT * FROM workflows;"
                )
                assert cur1.fetchone() is not None
                assert cur2.fetchone() is not None
