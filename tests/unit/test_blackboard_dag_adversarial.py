"""Adversarial stress-test suite for Blackboard DAG mechanics & concurrency (M2).

Exhaustively probes directed acyclic graph mechanics in src/neuri/core/blackboard.py:
1. Cycle detection: self-loops, 2-cycles, 3-cycles, deep 20-node cycles,
   disconnected subgraphs, multi-path cross-edges, diamond DAG preservation,
   and transitive shortcut edges.
2. Topological readiness (get_ready_nodes): single roots, linear chains,
   diamond DAG execution flow, failure blocking, cancellation blocking,
   multi-parent joins (N=5), fan-out, and active state exclusion.
3. Concurrency & SQLite WAL mode: concurrent multi-threaded writers, concurrent
   readers during active writes, and concurrent state transitions.
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
from typing import Any
import pytest

from neuri.core.blackboard import (
    Blackboard,
    BlackboardError,
    CycleDetectedError,
    InvalidStateTransitionError,
    NodeNotFoundError,
)
from neuri.core.schemas import TaskEdge, TaskNode, TaskState


@pytest.fixture
def bb(tmp_path: Path) -> Blackboard:
    """Provide a disk-backed Blackboard in a temporary directory.

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
    blackboard: Blackboard = Blackboard(db_file)
    return blackboard


class TestCycleDetectionAdversarial:
    """Adversarial test suite challenging DAG cycle detection algorithms."""

    def test_cycle_detection_self_loop_rejected(
        self, bb: Blackboard
    ) -> None:
        """Verify adding a self-loop edge A -> A is strictly rejected.

        Parameters
        ------------
        bb: Blackboard
            Initialized Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts exception on self-loop addition.
        """
        bb.create_workflow("wf-loop", "Self loop test")
        bb.create_node(
            TaskNode(
                node_id="A",
                workflow_id="wf-loop",
                agent_role="specialist",
                harness_id="agy",
            )
        )
        with pytest.raises((ValueError, BlackboardError)):
            bb.add_task_edge("wf-loop", "A", "A")

    def test_cycle_detection_self_loop_model_construct_bypass(
        self, bb: Blackboard
    ) -> None:
        """Verify self-loop is rejected even when bypassing Pydantic init.

        Parameters
        ------------
        bb: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts ValueError from Blackboard.add_edge validation.
        """
        bb.create_workflow("wf-bypass", "Bypass test")
        bb.create_node(
            TaskNode(
                node_id="A",
                workflow_id="wf-bypass",
                agent_role="specialist",
                harness_id="agy",
            )
        )
        raw_edge: TaskEdge = TaskEdge.model_construct(
            workflow_id="wf-bypass",
            parent_node_id="A",
            child_node_id="A",
        )
        with pytest.raises(ValueError):
            bb.add_edge(raw_edge)

    def test_cycle_detection_self_loop_sql_constraint(
        self, bb: Blackboard
    ) -> None:
        """Verify database CHECK constraint blocks direct self-loop insertion.

        Parameters
        ------------
        bb: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts sqlite3.IntegrityError on raw SQL self-loop insert.
        """
        bb.create_workflow("wf-sql-loop", "SQL loop test")
        bb.create_node(
            TaskNode(
                node_id="A",
                workflow_id="wf-sql-loop",
                agent_role="specialist",
                harness_id="agy",
            )
        )
        with pytest.raises(sqlite3.IntegrityError):
            with bb.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO task_edges (
                        workflow_id, parent_node_id, child_node_id
                    ) VALUES ('wf-sql-loop', 'A', 'A');
                    """
                )

    def test_cycle_detection_direct_2_cycle(self, bb: Blackboard) -> None:
        """Verify direct 2-cycle A -> B -> A is detected and blocked.

        Parameters
        ------------
        bb: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts CycleDetectedError on back-edge insertion.
        """
        bb.create_workflow("wf-2cyc", "2-cycle test")
        for nid in ("A", "B"):
            bb.create_node(
                TaskNode(
                    node_id=nid,
                    workflow_id="wf-2cyc",
                    agent_role="role",
                    harness_id="agy",
                )
            )
        bb.add_task_edge("wf-2cyc", "A", "B")
        with pytest.raises(CycleDetectedError):
            bb.add_task_edge("wf-2cyc", "B", "A")

    def test_cycle_detection_indirect_3_cycle(self, bb: Blackboard) -> None:
        """Verify indirect 3-cycle A -> B -> C -> A is detected and blocked.

        Parameters
        ------------
        bb: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts CycleDetectedError on closing edge.
        """
        bb.create_workflow("wf-3cyc", "3-cycle test")
        for nid in ("A", "B", "C"):
            bb.create_node(
                TaskNode(
                    node_id=nid,
                    workflow_id="wf-3cyc",
                    agent_role="role",
                    harness_id="agy",
                )
            )
        bb.add_task_edge("wf-3cyc", "A", "B")
        bb.add_task_edge("wf-3cyc", "B", "C")
        with pytest.raises(CycleDetectedError):
            bb.add_task_edge("wf-3cyc", "C", "A")

    def test_cycle_detection_deep_20_node_cycle(
        self, bb: Blackboard
    ) -> None:
        """Verify deep 20-node directed cycle is detected and blocked.

        Parameters
        ------------
        bb: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts CycleDetectedError on N19 -> N0 closing edge.
        """
        bb.create_workflow("wf-deep", "Deep cycle test")
        node_count: int = 20
        for i in range(node_count):
            bb.create_node(
                TaskNode(
                    node_id=f"N{i:02d}",
                    workflow_id="wf-deep",
                    agent_role="role",
                    harness_id="agy",
                )
            )
        for i in range(node_count - 1):
            bb.add_task_edge("wf-deep", f"N{i:02d}", f"N{i+1:02d}")

        with pytest.raises(CycleDetectedError) as exc_info:
            bb.add_task_edge("wf-deep", f"N{node_count-1:02d}", "N00")
        assert "creates a cycle" in str(exc_info.value)

    def test_cycle_detection_disconnected_subgraphs(
        self, bb: Blackboard
    ) -> None:
        """Verify cycle in one subgraph is caught without polluting others.

        Parameters
        ------------
        bb: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts cycle detection isolates disconnected component.
        """
        bb.create_workflow("wf-disc", "Disconnected subgraphs test")
        for nid in ("A", "B", "C", "X", "Y", "Z"):
            bb.create_node(
                TaskNode(
                    node_id=nid,
                    workflow_id="wf-disc",
                    agent_role="role",
                    harness_id="agy",
                )
            )
        # Component 1
        bb.add_task_edge("wf-disc", "A", "B")
        bb.add_task_edge("wf-disc", "B", "C")
        # Component 2
        bb.add_task_edge("wf-disc", "X", "Y")
        bb.add_task_edge("wf-disc", "Y", "Z")

        # Closing cycle in Component 2
        with pytest.raises(CycleDetectedError):
            bb.add_task_edge("wf-disc", "Z", "X")

        # Valid cross-edge connecting Component 1 to 2
        bb.add_task_edge("wf-disc", "C", "X")
        assert bb.validate_dag("wf-disc") is True

    def test_cycle_detection_multi_path_cross_edges(
        self, bb: Blackboard
    ) -> None:
        """Verify cycles are detected in graphs with cross and shortcut edges.

        Parameters
        ------------
        bb: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts CycleDetectedError on back-edges.
        """
        bb.create_workflow("wf-cross", "Cross edges test")
        for nid in ("A", "B", "C", "D"):
            bb.create_node(
                TaskNode(
                    node_id=nid,
                    workflow_id="wf-cross",
                    agent_role="role",
                    harness_id="agy",
                )
            )
        bb.add_task_edge("wf-cross", "A", "B")
        bb.add_task_edge("wf-cross", "A", "C")
        bb.add_task_edge("wf-cross", "B", "C")
        bb.add_task_edge("wf-cross", "C", "D")

        with pytest.raises(CycleDetectedError):
            bb.add_task_edge("wf-cross", "D", "A")

        with pytest.raises(CycleDetectedError):
            bb.add_task_edge("wf-cross", "C", "A")

    def test_diamond_dag_preserved_not_rejected(
        self, bb: Blackboard
    ) -> None:
        """Verify diamond DAG A -> (B, C) -> D is accepted as valid DAG.

        Parameters
        ------------
        bb: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts diamond graph is valid and preserves topological order.
        """
        bb.create_workflow("wf-diamond", "Diamond preservation test")
        for nid in ("A", "B", "C", "D"):
            bb.create_node(
                TaskNode(
                    node_id=nid,
                    workflow_id="wf-diamond",
                    agent_role="role",
                    harness_id="agy",
                )
            )
        bb.add_task_edge("wf-diamond", "A", "B")
        bb.add_task_edge("wf-diamond", "A", "C")
        bb.add_task_edge("wf-diamond", "B", "D")
        bb.add_task_edge("wf-diamond", "C", "D")

        assert bb.validate_dag("wf-diamond") is True
        topo: list[str] = bb.get_topological_order("wf-diamond")
        assert topo[0] == "A"
        assert topo[-1] == "D"
        assert set(topo[1:3]) == {"B", "C"}

    def test_multi_diamond_hourglass_dag(self, bb: Blackboard) -> None:
        """Verify complex multi-diamond hourglass DAG is preserved.

        Parameters
        ------------
        bb: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts valid multi-diamond DAG validation.
        """
        bb.create_workflow("wf-hourglass", "Hourglass test")
        nodes: tuple[str, ...] = ("A", "B", "C", "D", "E", "F", "G")
        for nid in nodes:
            bb.create_node(
                TaskNode(
                    node_id=nid,
                    workflow_id="wf-hourglass",
                    agent_role="role",
                    harness_id="agy",
                )
            )
        # Top diamond
        bb.add_task_edge("wf-hourglass", "A", "B")
        bb.add_task_edge("wf-hourglass", "A", "C")
        bb.add_task_edge("wf-hourglass", "B", "D")
        bb.add_task_edge("wf-hourglass", "C", "D")
        # Bottom diamond
        bb.add_task_edge("wf-hourglass", "D", "E")
        bb.add_task_edge("wf-hourglass", "D", "F")
        bb.add_task_edge("wf-hourglass", "E", "G")
        bb.add_task_edge("wf-hourglass", "F", "G")

        assert bb.validate_dag("wf-hourglass") is True
        topo: list[str] = bb.get_topological_order("wf-hourglass")
        assert topo.index("A") < topo.index("D")
        assert topo.index("D") < topo.index("G")

    def test_transitive_shortcut_edge(self, bb: Blackboard) -> None:
        """Verify transitive shortcut edge A -> C in A -> B -> C is valid.

        Parameters
        ------------
        bb: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts valid DAG with transitive edge.
        """
        bb.create_workflow("wf-trans", "Transitive test")
        for nid in ("A", "B", "C"):
            bb.create_node(
                TaskNode(
                    node_id=nid,
                    workflow_id="wf-trans",
                    agent_role="role",
                    harness_id="agy",
                )
            )
        bb.add_task_edge("wf-trans", "A", "B")
        bb.add_task_edge("wf-trans", "B", "C")
        bb.add_task_edge("wf-trans", "A", "C")

        assert bb.validate_dag("wf-trans") is True
        topo: list[str] = bb.get_topological_order("wf-trans")
        assert topo == ["A", "B", "C"]

    def test_duplicate_edge_addition_idempotency(
        self, bb: Blackboard
    ) -> None:
        """Verify re-adding identical edge is idempotent and does not error.

        Parameters
        ------------
        bb: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts duplicate edge ignored without error.
        """
        bb.create_workflow("wf-idemp", "Idempotent edge test")
        for nid in ("A", "B"):
            bb.create_node(
                TaskNode(
                    node_id=nid,
                    workflow_id="wf-idemp",
                    agent_role="role",
                    harness_id="agy",
                )
            )
        bb.add_task_edge("wf-idemp", "A", "B")
        bb.add_task_edge("wf-idemp", "A", "B")
        edges = bb.get_edges("wf-idemp")
        assert len(edges) == 1


class TestGetReadyNodesAdversarial:
    """Adversarial test suite challenging get_ready_nodes topological queries."""

    def test_get_ready_nodes_linear_pipeline_lifecycle(
        self, bb: Blackboard
    ) -> None:
        """Verify step-by-step unblocking in linear chain A -> B -> C.

        Parameters
        ------------
        bb: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts sequential readiness through lifecycle.
        """
        bb.create_workflow("wf-linear", "Linear test")
        for nid in ("A", "B", "C"):
            bb.create_node(
                TaskNode(
                    node_id=nid,
                    workflow_id="wf-linear",
                    agent_role="role",
                    harness_id="agy",
                )
            )
        bb.add_task_edge("wf-linear", "A", "B")
        bb.add_task_edge("wf-linear", "B", "C")

        # Step 1: Initial state -> only A is ready
        assert [n.node_id for n in bb.get_ready_nodes("wf-linear")] == ["A"]

        # Step 2: A is RUNNING -> no nodes ready
        bb.update_node_state("A", TaskState.RUNNING)
        assert bb.get_ready_nodes("wf-linear") == []

        # Step 3: A is COMPLETED -> only B is ready
        bb.update_node_state("A", TaskState.COMPLETED)
        assert [n.node_id for n in bb.get_ready_nodes("wf-linear")] == ["B"]

        # Step 4: B is RUNNING -> no nodes ready
        bb.update_node_state("B", TaskState.RUNNING)
        assert bb.get_ready_nodes("wf-linear") == []

        # Step 5: B is COMPLETED -> only C is ready
        bb.update_node_state("B", TaskState.COMPLETED)
        assert [n.node_id for n in bb.get_ready_nodes("wf-linear")] == ["C"]

        # Step 6: C is COMPLETED -> all completed, ready is empty
        bb.update_node_state("C", TaskState.RUNNING)
        bb.update_node_state("C", TaskState.COMPLETED)
        assert bb.get_ready_nodes("wf-linear") == []

    def test_get_ready_nodes_diamond_dag_branching(
        self, bb: Blackboard
    ) -> None:
        """Verify diamond DAG readiness: D waits until both B and C complete.

        Parameters
        ------------
        bb: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts D remains blocked until all parents complete.
        """
        bb.create_workflow("wf-dia-sched", "Diamond schedule test")
        for nid in ("A", "B", "C", "D"):
            bb.create_node(
                TaskNode(
                    node_id=nid,
                    workflow_id="wf-dia-sched",
                    agent_role="role",
                    harness_id="agy",
                )
            )
        bb.add_task_edge("wf-dia-sched", "A", "B")
        bb.add_task_edge("wf-dia-sched", "A", "C")
        bb.add_task_edge("wf-dia-sched", "B", "D")
        bb.add_task_edge("wf-dia-sched", "C", "D")

        # A completes
        bb.update_node_state("A", TaskState.RUNNING)
        bb.update_node_state("A", TaskState.COMPLETED)

        # Both B and C are ready
        ready_ids: set[str] = {
            n.node_id for n in bb.get_ready_nodes("wf-dia-sched")
        }
        assert ready_ids == {"B", "C"}

        # B completes, C is still PENDING -> D must NOT be ready
        bb.update_node_state("B", TaskState.RUNNING)
        bb.update_node_state("B", TaskState.COMPLETED)
        assert [
            n.node_id for n in bb.get_ready_nodes("wf-dia-sched")
        ] == ["C"]

        # C completes -> D becomes ready
        bb.update_node_state("C", TaskState.RUNNING)
        bb.update_node_state("C", TaskState.COMPLETED)
        assert [
            n.node_id for n in bb.get_ready_nodes("wf-dia-sched")
        ] == ["D"]

    def test_get_ready_nodes_blocked_when_one_diamond_branch_fails(
        self, bb: Blackboard
    ) -> None:
        """Verify D is permanently blocked if sibling B fails even if C completes.

        Parameters
        ------------
        bb: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts D blocked and reported in get_blocked_nodes.
        """
        bb.create_workflow("wf-dia-fail", "Diamond failure test")
        for nid in ("A", "B", "C", "D"):
            bb.create_node(
                TaskNode(
                    node_id=nid,
                    workflow_id="wf-dia-fail",
                    agent_role="role",
                    harness_id="agy",
                )
            )
        bb.add_task_edge("wf-dia-fail", "A", "B")
        bb.add_task_edge("wf-dia-fail", "A", "C")
        bb.add_task_edge("wf-dia-fail", "B", "D")
        bb.add_task_edge("wf-dia-fail", "C", "D")

        bb.update_node_state("A", TaskState.RUNNING)
        bb.update_node_state("A", TaskState.COMPLETED)

        # B fails
        bb.update_node_state("B", TaskState.RUNNING)
        bb.update_node_state("B", TaskState.FAILED, "OOM error")

        # C completes
        bb.update_node_state("C", TaskState.RUNNING)
        bb.update_node_state("C", TaskState.COMPLETED)

        # D must be blocked
        ready = bb.get_ready_nodes("wf-dia-fail")
        assert ready == []

        blocked = bb.get_blocked_nodes("wf-dia-fail")
        assert len(blocked) == 1
        assert blocked[0][0].node_id == "D"
        assert "B" in blocked[0][1]

    def test_get_ready_nodes_parent_cancelled_blocks_children(
        self, bb: Blackboard
    ) -> None:
        """Verify cancelling parent blocks all dependent children.

        Parameters
        ------------
        bb: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts children blocked on parent cancellation.
        """
        bb.create_workflow("wf-canc", "Cancellation test")
        for nid in ("root", "child1", "child2"):
            bb.create_node(
                TaskNode(
                    node_id=nid,
                    workflow_id="wf-canc",
                    agent_role="role",
                    harness_id="agy",
                )
            )
        bb.add_task_edge("wf-canc", "root", "child1")
        bb.add_task_edge("wf-canc", "root", "child2")

        bb.update_node_state("root", TaskState.CANCELLED)

        assert bb.get_ready_nodes("wf-canc") == []
        blocked = bb.get_blocked_nodes("wf-canc")
        blocked_node_ids = {item[0].node_id for item in blocked}
        assert blocked_node_ids == {"child1", "child2"}

    def test_get_ready_nodes_multi_parent_join_five_parents(
        self, bb: Blackboard
    ) -> None:
        """Verify node with 5 parents is ready only when all 5 are completed.

        Parameters
        ------------
        bb: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts child unblocked strictly on 5th parent completion.
        """
        bb.create_workflow("wf-multi-p", "Multi parent test")
        for i in range(5):
            bb.create_node(
                TaskNode(
                    node_id=f"P{i}",
                    workflow_id="wf-multi-p",
                    agent_role="role",
                    harness_id="agy",
                )
            )
        bb.create_node(
            TaskNode(
                node_id="Child",
                workflow_id="wf-multi-p",
                agent_role="role",
                harness_id="agy",
            )
        )
        for i in range(5):
            bb.add_task_edge("wf-multi-p", f"P{i}", "Child")

        # Complete parents P0..P3
        for i in range(4):
            bb.update_node_state(f"P{i}", TaskState.RUNNING)
            bb.update_node_state(f"P{i}", TaskState.COMPLETED)
            assert bb.get_ready_nodes("wf-multi-p") == [
                bb.get_node("P4")  # P4 is still pending
            ]

        # Complete P4 -> Child is now ready
        bb.update_node_state("P4", TaskState.RUNNING)
        bb.update_node_state("P4", TaskState.COMPLETED)

        ready_nodes = bb.get_ready_nodes("wf-multi-p")
        assert len(ready_nodes) == 1
        assert ready_nodes[0].node_id == "Child"

    def test_get_ready_nodes_fan_out_multi_child(
        self, bb: Blackboard
    ) -> None:
        """Verify parent completing simultaneously unblocks multiple children.

        Parameters
        ------------
        bb: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts all children ready upon parent completion.
        """
        bb.create_workflow("wf-fan", "Fan out test")
        bb.create_node(
            TaskNode(
                node_id="Root",
                workflow_id="wf-fan",
                agent_role="role",
                harness_id="agy",
            )
        )
        for i in range(4):
            bb.create_node(
                TaskNode(
                    node_id=f"Child{i}",
                    workflow_id="wf-fan",
                    agent_role="role",
                    harness_id="agy",
                )
            )
            bb.add_task_edge("wf-fan", "Root", f"Child{i}")

        bb.update_node_state("Root", TaskState.RUNNING)
        bb.update_node_state("Root", TaskState.COMPLETED)

        ready = bb.get_ready_nodes("wf-fan")
        ready_ids = {n.node_id for n in ready}
        assert ready_ids == {"Child0", "Child1", "Child2", "Child3"}

    def test_get_ready_nodes_excludes_active_non_pending_states(
        self, bb: Blackboard
    ) -> None:
        """Verify nodes in RUNNING, PREFLIGHT, or RETRYING are not ready.

        Parameters
        ------------
        bb: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts non-pending states excluded from ready query.
        """
        bb.create_workflow("wf-states", "State exclusion test")
        for nid in ("N-running", "N-preflight", "N-retrying"):
            bb.create_node(
                TaskNode(
                    node_id=nid,
                    workflow_id="wf-states",
                    agent_role="role",
                    harness_id="agy",
                )
            )
        bb.update_node_state("N-running", TaskState.RUNNING)
        bb.update_node_state("N-preflight", TaskState.PREFLIGHT_CHECK)
        bb.update_node_state("N-retrying", TaskState.RUNNING)
        bb.update_node_state("N-retrying", TaskState.RETRYING)

        ready = bb.get_ready_nodes("wf-states")
        assert ready == []


class TestBlackboardConcurrencyAdversarial:
    """Adversarial test suite challenging SQLite WAL concurrency & integrity."""

    def test_concurrent_multi_threaded_node_insertions(
        self, bb: Blackboard
    ) -> None:
        """Verify 10 concurrent threads inserting nodes into SQLite WAL mode.

        Parameters
        ------------
        bb: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts all 100 concurrently inserted nodes exist.
        """
        bb.create_workflow("wf-con-insert", "Concurrent insert test")
        thread_count: int = 10
        nodes_per_thread: int = 10

        def insert_worker(thread_idx: int) -> list[str]:
            created: list[str] = []
            for j in range(nodes_per_thread):
                nid: str = f"t{thread_idx}-node{j}"
                node: TaskNode = TaskNode(
                    node_id=nid,
                    workflow_id="wf-con-insert",
                    agent_role="worker",
                    harness_id="codex",
                )
                bb.create_node(node)
                created.append(nid)
            return created

        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            futures = [
                executor.submit(insert_worker, idx)
                for idx in range(thread_count)
            ]
            for f in futures:
                f.result()

        all_nodes = bb.get_nodes_by_workflow("wf-con-insert")
        assert len(all_nodes) == thread_count * nodes_per_thread

    def test_concurrent_readers_during_active_writer(
        self, bb: Blackboard
    ) -> None:
        """Verify readers do not block writer and queries succeed concurrently.

        Parameters
        ------------
        bb: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts zero lock failures during simultaneous read/write load.
        """
        bb.create_workflow("wf-con-rw", "Read write concurrency test")

        def writer() -> None:
            for i in range(25):
                bb.create_node(
                    TaskNode(
                        node_id=f"rw-node-{i}",
                        workflow_id="wf-con-rw",
                        agent_role="writer",
                        harness_id="agy",
                    )
                )

        def reader() -> list[int]:
            counts: list[int] = []
            for _ in range(25):
                ready = bb.get_ready_nodes("wf-con-rw")
                counts.append(len(ready))
            return counts

        with ThreadPoolExecutor(max_workers=5) as executor:
            writer_future = executor.submit(writer)
            reader_futures = [executor.submit(reader) for _ in range(4)]

            writer_future.result()
            for rf in reader_futures:
                results = rf.result()
                assert len(results) == 25

        final_nodes = bb.get_nodes_by_workflow("wf-con-rw")
        assert len(final_nodes) == 25

    def test_concurrent_node_state_transitions(
        self, bb: Blackboard
    ) -> None:
        """Verify 5 concurrent threads updating different node states.

        Parameters
        ------------
        bb: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts all state transitions persisted accurately.
        """
        bb.create_workflow("wf-con-state", "Concurrent state test")
        node_count: int = 20
        for i in range(node_count):
            bb.create_node(
                TaskNode(
                    node_id=f"state-node-{i}",
                    workflow_id="wf-con-state",
                    agent_role="specialist",
                    harness_id="agy",
                )
            )

        def transition_worker(node_idx: int) -> None:
            nid: str = f"state-node-{node_idx}"
            bb.update_node_state(nid, TaskState.RUNNING)
            bb.update_node_state(nid, TaskState.COMPLETED)

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(transition_worker, i) for i in range(node_count)
            ]
            for f in futures:
                f.result()

        nodes = bb.get_nodes_by_workflow("wf-con-state")
        assert len(nodes) == node_count
        assert all(n.state == TaskState.COMPLETED for n in nodes)


class TestBlackboardStructuralIntegrityAdversarial:
    """Adversarial test suite verifying relational cascades and boundary conditions."""

    def test_cascade_delete_node_removes_edges_and_unblocks_children(
        self, bb: Blackboard
    ) -> None:
        """Verify deleting parent cascades to remove edges and unblocks child.

        Parameters
        ------------
        bb: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts cascade edge removal and child becoming root.
        """
        bb.create_workflow("wf-casc", "Cascade test")
        bb.create_node(
            TaskNode(
                node_id="parent-del",
                workflow_id="wf-casc",
                agent_role="role",
                harness_id="agy",
            )
        )
        bb.create_node(
            TaskNode(
                node_id="child-live",
                workflow_id="wf-casc",
                agent_role="role",
                harness_id="agy",
            )
        )
        bb.add_task_edge("wf-casc", "parent-del", "child-live")

        # Child is initially blocked by parent-del
        assert bb.get_ready_nodes("wf-casc") == [bb.get_node("parent-del")]

        # Delete parent node
        bb.delete_task_node("parent-del")

        # Edges should be cascaded
        edges = bb.get_edges("wf-casc")
        assert edges == []

        # Child is now root and ready
        ready = bb.get_ready_nodes("wf-casc")
        assert len(ready) == 1
        assert ready[0].node_id == "child-live"

    def test_cross_workflow_node_isolation(self, bb: Blackboard) -> None:
        """Verify edge cannot connect nodes across two different workflows.

        Parameters
        ------------
        bb: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts NodeNotFoundError when connecting cross-workflow nodes.
        """
        bb.create_workflow("wf-1", "Workflow 1")
        bb.create_workflow("wf-2", "Workflow 2")

        bb.create_node(
            TaskNode(
                node_id="node-wf1",
                workflow_id="wf-1",
                agent_role="role",
                harness_id="agy",
            )
        )
        bb.create_node(
            TaskNode(
                node_id="node-wf2",
                workflow_id="wf-2",
                agent_role="role",
                harness_id="agy",
            )
        )

        with pytest.raises(NodeNotFoundError):
            bb.add_task_edge("wf-1", "node-wf1", "node-wf2")

    def test_invalid_state_transition_matrix_rejection(
        self, bb: Blackboard
    ) -> None:
        """Verify illegal transitions are rejected according to state machine.

        Parameters
        ------------
        bb: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts InvalidStateTransitionError on forbidden transitions.
        """
        bb.create_workflow("wf-matrix", "Matrix test")
        bb.create_node(
            TaskNode(
                node_id="test-node",
                workflow_id="wf-matrix",
                agent_role="role",
                harness_id="agy",
            )
        )
        # PENDING -> COMPLETED is illegal
        with pytest.raises(InvalidStateTransitionError):
            bb.update_node_state("test-node", TaskState.COMPLETED)

        # Move to COMPLETED legitimately
        bb.update_node_state("test-node", TaskState.RUNNING)
        bb.update_node_state("test-node", TaskState.COMPLETED)

        # COMPLETED is terminal -> cannot transition to RUNNING
        with pytest.raises(InvalidStateTransitionError):
            bb.update_node_state("test-node", TaskState.RUNNING)
