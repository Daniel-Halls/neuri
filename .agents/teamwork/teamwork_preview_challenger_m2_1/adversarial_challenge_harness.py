"""Standalone Empirical Challenge Harness for Blackboard DAG & Concurrency (M2).

Runs white-box stress probes directly against Blackboard in a temporary SQLite DB:
1. Self-loops (A->A)
2. Direct 2-cycles (A->B->A)
3. Indirect 3-cycles (A->B->C->A)
4. Deep 20-node cycles (N0->...->N19->N0)
5. Diamond DAG preservation (A->B, A->C, B->D, C->D)
6. Multi-diamond hourglass DAG
7. Transitive shortcut edges
8. Topological readiness (get_ready_nodes) diamond lifecycle
9. Diamond failure blocking (B fails, D blocked)
10. Parent cancellation blocking
11. Multi-parent joins (5 parents)
12. Concurrent multi-threaded writers in WAL mode
13. Concurrent readers during active writes
14. Concurrent state transitions
15. Relational cascade on node deletion
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import sqlite3
import tempfile
from typing import Any

from neuri.core.blackboard import (
    Blackboard,
    BlackboardError,
    CycleDetectedError,
    InvalidStateTransitionError,
    NodeNotFoundError,
)
from neuri.core.schemas import TaskEdge, TaskNode, TaskState


def run_all_challenges() -> dict[str, Any]:
    """Execute all empirical challenge probes and collect detailed logs.

    Parameters
    ------------
    None

    Returns
    --------
        dict[str, Any]: dictionary object
            Dictionary with probe names, outcomes, and log messages.
    """
    tmp_dir: Path = Path(tempfile.mkdtemp(prefix="neuri_m2_challenger_"))
    db_file: Path = tmp_dir / "challenge.db"
    bb: Blackboard = Blackboard(db_file)
    results: dict[str, Any] = {}
    logs: list[str] = []

    try:
        # Probe 1: Self-loop direct
        bb.create_workflow("wf-1", "Self-loop probe")
        bb.create_node(
            TaskNode(
                node_id="A",
                workflow_id="wf-1",
                agent_role="role",
                harness_id="agy",
            )
        )
        self_loop_caught = False
        try:
            bb.add_task_edge("wf-1", "A", "A")
        except (ValueError, BlackboardError):
            self_loop_caught = True
        results["probe_1_self_loop"] = "PASS" if self_loop_caught else "FAIL"
        logs.append(f"Probe 1 (Self-loop rejection): {results['probe_1_self_loop']}")

        # Probe 2: Direct 2-cycle
        bb.create_workflow("wf-2", "2-cycle probe")
        for nid in ("A", "B"):
            bb.create_node(
                TaskNode(
                    node_id=nid,
                    workflow_id="wf-2",
                    agent_role="role",
                    harness_id="agy",
                )
            )
        bb.add_task_edge("wf-2", "A", "B")
        cycle_2_caught = False
        try:
            bb.add_task_edge("wf-2", "B", "A")
        except CycleDetectedError:
            cycle_2_caught = True
        results["probe_2_direct_2_cycle"] = "PASS" if cycle_2_caught else "FAIL"
        logs.append(f"Probe 2 (Direct 2-cycle detection): {results['probe_2_direct_2_cycle']}")

        # Probe 3: Indirect 3-cycle
        bb.create_workflow("wf-3", "3-cycle probe")
        for nid in ("A", "B", "C"):
            bb.create_node(
                TaskNode(
                    node_id=nid,
                    workflow_id="wf-3",
                    agent_role="role",
                    harness_id="agy",
                )
            )
        bb.add_task_edge("wf-3", "A", "B")
        bb.add_task_edge("wf-3", "B", "C")
        cycle_3_caught = False
        try:
            bb.add_task_edge("wf-3", "C", "A")
        except CycleDetectedError:
            cycle_3_caught = True
        results["probe_3_indirect_3_cycle"] = "PASS" if cycle_3_caught else "FAIL"
        logs.append(f"Probe 3 (Indirect 3-cycle detection): {results['probe_3_indirect_3_cycle']}")

        # Probe 4: Deep 20-node cycle
        bb.create_workflow("wf-4", "Deep cycle probe")
        for i in range(20):
            bb.create_node(
                TaskNode(
                    node_id=f"D{i:02d}",
                    workflow_id="wf-4",
                    agent_role="role",
                    harness_id="agy",
                )
            )
        for i in range(19):
            bb.add_task_edge("wf-4", f"D{i:02d}", f"D{i+1:02d}")
        deep_cycle_caught = False
        try:
            bb.add_task_edge("wf-4", "D19", "D00")
        except CycleDetectedError:
            deep_cycle_caught = True
        results["probe_4_deep_20_node_cycle"] = "PASS" if deep_cycle_caught else "FAIL"
        logs.append(f"Probe 4 (Deep 20-node cycle detection): {results['probe_4_deep_20_node_cycle']}")

        # Probe 5: Diamond DAG preservation
        bb.create_workflow("wf-5", "Diamond probe")
        for nid in ("A", "B", "C", "D"):
            bb.create_node(
                TaskNode(
                    node_id=nid,
                    workflow_id="wf-5",
                    agent_role="role",
                    harness_id="agy",
                )
            )
        bb.add_task_edge("wf-5", "A", "B")
        bb.add_task_edge("wf-5", "A", "C")
        bb.add_task_edge("wf-5", "B", "D")
        bb.add_task_edge("wf-5", "C", "D")
        diamond_valid = bb.validate_dag("wf-5")
        topo = bb.get_topological_order("wf-5")
        diamond_ok = diamond_valid and topo[0] == "A" and topo[-1] == "D"
        results["probe_5_diamond_preservation"] = "PASS" if diamond_ok else "FAIL"
        logs.append(f"Probe 5 (Diamond DAG preservation): {results['probe_5_diamond_preservation']}")

        # Probe 6: Multi-diamond hourglass DAG
        bb.create_workflow("wf-6", "Hourglass probe")
        for nid in ("A", "B", "C", "D", "E", "F", "G"):
            bb.create_node(
                TaskNode(
                    node_id=nid,
                    workflow_id="wf-6",
                    agent_role="role",
                    harness_id="agy",
                )
            )
        bb.add_task_edge("wf-6", "A", "B")
        bb.add_task_edge("wf-6", "A", "C")
        bb.add_task_edge("wf-6", "B", "D")
        bb.add_task_edge("wf-6", "C", "D")
        bb.add_task_edge("wf-6", "D", "E")
        bb.add_task_edge("wf-6", "D", "F")
        bb.add_task_edge("wf-6", "E", "G")
        bb.add_task_edge("wf-6", "F", "G")
        hg_valid = bb.validate_dag("wf-6")
        results["probe_6_hourglass_dag"] = "PASS" if hg_valid else "FAIL"
        logs.append(f"Probe 6 (Multi-diamond hourglass DAG): {results['probe_6_hourglass_dag']}")

        # Probe 7: Transitive shortcut edge
        bb.create_workflow("wf-7", "Transitive probe")
        for nid in ("A", "B", "C"):
            bb.create_node(
                TaskNode(
                    node_id=nid,
                    workflow_id="wf-7",
                    agent_role="role",
                    harness_id="agy",
                )
            )
        bb.add_task_edge("wf-7", "A", "B")
        bb.add_task_edge("wf-7", "B", "C")
        bb.add_task_edge("wf-7", "A", "C")
        trans_valid = bb.validate_dag("wf-7")
        results["probe_7_transitive_edge"] = "PASS" if trans_valid else "FAIL"
        logs.append(f"Probe 7 (Transitive shortcut edge): {results['probe_7_transitive_edge']}")

        # Probe 8: Diamond execution sequence
        bb.create_workflow("wf-8", "Diamond execution probe")
        for nid in ("A", "B", "C", "D"):
            bb.create_node(
                TaskNode(
                    node_id=nid,
                    workflow_id="wf-8",
                    agent_role="role",
                    harness_id="agy",
                )
            )
        bb.add_task_edge("wf-8", "A", "B")
        bb.add_task_edge("wf-8", "A", "C")
        bb.add_task_edge("wf-8", "B", "D")
        bb.add_task_edge("wf-8", "C", "D")

        seq_1 = [n.node_id for n in bb.get_ready_nodes("wf-8")] == ["A"]
        bb.update_node_state("A", TaskState.RUNNING)
        bb.update_node_state("A", TaskState.COMPLETED)
        seq_2 = {n.node_id for n in bb.get_ready_nodes("wf-8")} == {"B", "C"}
        bb.update_node_state("B", TaskState.RUNNING)
        bb.update_node_state("B", TaskState.COMPLETED)
        seq_3 = [n.node_id for n in bb.get_ready_nodes("wf-8")] == ["C"]
        bb.update_node_state("C", TaskState.RUNNING)
        bb.update_node_state("C", TaskState.COMPLETED)
        seq_4 = [n.node_id for n in bb.get_ready_nodes("wf-8")] == ["D"]
        bb.update_node_state("D", TaskState.RUNNING)
        bb.update_node_state("D", TaskState.COMPLETED)
        seq_5 = bb.get_ready_nodes("wf-8") == []
        diamond_seq_ok = seq_1 and seq_2 and seq_3 and seq_4 and seq_5
        results["probe_8_diamond_execution_flow"] = "PASS" if diamond_seq_ok else "FAIL"
        logs.append(f"Probe 8 (Diamond execution sequence): {results['probe_8_diamond_execution_flow']}")

        # Probe 9: Diamond branch failure blocking
        bb.create_workflow("wf-9", "Diamond failure probe")
        for nid in ("A", "B", "C", "D"):
            bb.create_node(
                TaskNode(
                    node_id=nid,
                    workflow_id="wf-9",
                    agent_role="role",
                    harness_id="agy",
                )
            )
        bb.add_task_edge("wf-9", "A", "B")
        bb.add_task_edge("wf-9", "A", "C")
        bb.add_task_edge("wf-9", "B", "D")
        bb.add_task_edge("wf-9", "C", "D")
        bb.update_node_state("A", TaskState.RUNNING)
        bb.update_node_state("A", TaskState.COMPLETED)
        bb.update_node_state("B", TaskState.RUNNING)
        bb.update_node_state("B", TaskState.FAILED, "Out of memory")
        bb.update_node_state("C", TaskState.RUNNING)
        bb.update_node_state("C", TaskState.COMPLETED)
        ready_9 = bb.get_ready_nodes("wf-9")
        blocked_9 = bb.get_blocked_nodes("wf-9")
        fail_block_ok = len(ready_9) == 0 and len(blocked_9) == 1 and blocked_9[0][0].node_id == "D"
        results["probe_9_diamond_failure_blocking"] = "PASS" if fail_block_ok else "FAIL"
        logs.append(f"Probe 9 (Diamond branch failure blocking): {results['probe_9_diamond_failure_blocking']}")

        # Probe 10: Parent cancellation blocking
        bb.create_workflow("wf-10", "Cancellation probe")
        for nid in ("P", "C1", "C2"):
            bb.create_node(
                TaskNode(
                    node_id=nid,
                    workflow_id="wf-10",
                    agent_role="role",
                    harness_id="agy",
                )
            )
        bb.add_task_edge("wf-10", "P", "C1")
        bb.add_task_edge("wf-10", "P", "C2")
        bb.update_node_state("P", TaskState.CANCELLED)
        ready_10 = bb.get_ready_nodes("wf-10")
        blocked_10 = bb.get_blocked_nodes("wf-10")
        canc_block_ok = len(ready_10) == 0 and len(blocked_10) == 2
        results["probe_10_cancellation_blocking"] = "PASS" if canc_block_ok else "FAIL"
        logs.append(f"Probe 10 (Parent cancellation blocking): {results['probe_10_cancellation_blocking']}")

        # Probe 11: Multi-parent join (5 parents)
        bb.create_workflow("wf-11", "Multi-parent probe")
        for i in range(5):
            bb.create_node(
                TaskNode(
                    node_id=f"P{i}",
                    workflow_id="wf-11",
                    agent_role="role",
                    harness_id="agy",
                )
            )
        bb.create_node(
            TaskNode(
                node_id="Child",
                workflow_id="wf-11",
                agent_role="role",
                harness_id="agy",
            )
        )
        for i in range(5):
            bb.add_task_edge("wf-11", f"P{i}", "Child")
        for i in range(4):
            bb.update_node_state(f"P{i}", TaskState.RUNNING)
            bb.update_node_state(f"P{i}", TaskState.COMPLETED)
        not_ready_yet = len(bb.get_ready_nodes("wf-11")) == 1  # P4 is pending, Child not ready
        bb.update_node_state("P4", TaskState.RUNNING)
        bb.update_node_state("P4", TaskState.COMPLETED)
        now_ready = [n.node_id for n in bb.get_ready_nodes("wf-11")] == ["Child"]
        multi_p_ok = not_ready_yet and now_ready
        results["probe_11_multi_parent_join"] = "PASS" if multi_p_ok else "FAIL"
        logs.append(f"Probe 11 (Multi-parent 5-way join): {results['probe_11_multi_parent_join']}")

        # Probe 12: Concurrent writers in WAL mode
        bb.create_workflow("wf-12", "Concurrent writers probe")
        thread_count: int = 10
        nodes_per_thread: int = 10

        def write_task(t_idx: int) -> None:
            for j in range(nodes_per_thread):
                bb.create_node(
                    TaskNode(
                        node_id=f"T{t_idx}-N{j}",
                        workflow_id="wf-12",
                        agent_role="worker",
                        harness_id="agy",
                    )
                )

        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            futs = [executor.submit(write_task, idx) for idx in range(thread_count)]
            for f in futs:
                f.result()

        total_nodes = len(bb.get_nodes_by_workflow("wf-12"))
        con_write_ok = total_nodes == thread_count * nodes_per_thread
        results["probe_12_concurrent_writers_wal"] = "PASS" if con_write_ok else "FAIL"
        logs.append(f"Probe 12 (Concurrent multi-threaded writers): {results['probe_12_concurrent_writers_wal']}")

        # Probe 13: Concurrent readers during active writer
        bb.create_workflow("wf-13", "Concurrent RW probe")

        def writer_13() -> None:
            for i in range(30):
                bb.create_node(
                    TaskNode(
                        node_id=f"RW-{i}",
                        workflow_id="wf-13",
                        agent_role="writer",
                        harness_id="agy",
                    )
                )

        def reader_13() -> int:
            success_count: int = 0
            for _ in range(30):
                bb.get_ready_nodes("wf-13")
                success_count += 1
            return success_count

        with ThreadPoolExecutor(max_workers=5) as executor:
            w_fut = executor.submit(writer_13)
            r_futs = [executor.submit(reader_13) for _ in range(4)]
            w_fut.result()
            r_results = [rf.result() for rf in r_futs]
        con_rw_ok = all(cnt == 30 for cnt in r_results)
        results["probe_13_concurrent_readers_during_writes"] = "PASS" if con_rw_ok else "FAIL"
        logs.append(f"Probe 13 (Concurrent readers during writes): {results['probe_13_concurrent_readers_during_writes']}")

        # Probe 14: Concurrent state transitions
        bb.create_workflow("wf-14", "Concurrent transitions probe")
        for i in range(20):
            bb.create_node(
                TaskNode(
                    node_id=f"ST-{i}",
                    workflow_id="wf-14",
                    agent_role="role",
                    harness_id="agy",
                )
            )

        def trans_task(idx: int) -> None:
            bb.update_node_state(f"ST-{idx}", TaskState.RUNNING)
            bb.update_node_state(f"ST-{idx}", TaskState.COMPLETED)

        with ThreadPoolExecutor(max_workers=5) as executor:
            futs = [executor.submit(trans_task, idx) for idx in range(20)]
            for f in futs:
                f.result()
        st_nodes = bb.get_nodes_by_workflow("wf-14")
        con_st_ok = all(n.state == TaskState.COMPLETED for n in st_nodes)
        results["probe_14_concurrent_state_transitions"] = "PASS" if con_st_ok else "FAIL"
        logs.append(f"Probe 14 (Concurrent state transitions): {results['probe_14_concurrent_state_transitions']}")

        # Probe 15: Cascade delete node unblocks child
        bb.create_workflow("wf-15", "Cascade probe")
        bb.create_node(
            TaskNode(
                node_id="P_del",
                workflow_id="wf-15",
                agent_role="role",
                harness_id="agy",
            )
        )
        bb.create_node(
            TaskNode(
                node_id="C_live",
                workflow_id="wf-15",
                agent_role="role",
                harness_id="agy",
            )
        )
        bb.add_task_edge("wf-15", "P_del", "C_live")
        bb.delete_task_node("P_del")
        ready_15 = bb.get_ready_nodes("wf-15")
        casc_ok = len(ready_15) == 1 and ready_15[0].node_id == "C_live"
        results["probe_15_cascade_delete_unblocks"] = "PASS" if casc_ok else "FAIL"
        logs.append(f"Probe 15 (Cascade delete unblocks child): {results['probe_15_cascade_delete_unblocks']}")

    finally:
        bb.close()
        shutil.rmtree(tmp_dir, ignore_errors=True)

    summary_dict: dict[str, Any] = {
        "results": results,
        "logs": logs,
        "all_passed": all(v == "PASS" for v in results.values()),
        "total_probes": len(results),
        "passed_probes": sum(1 for v in results.values() if v == "PASS"),
    }
    return summary_dict


if __name__ == "__main__":
    outcome = run_all_challenges()
    print("=" * 60)
    print("NEURI M2 EMPIRICAL DAG CHALLENGE HARNESS EXECUTION SUMMARY")
    print("=" * 60)
    for line in outcome["logs"]:
        print(line)
    print("=" * 60)
    print(f"Total: {outcome['total_probes']} | Passed: {outcome['passed_probes']} | All Passed: {outcome['all_passed']}")
