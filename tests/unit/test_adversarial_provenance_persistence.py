"""Adversarial Provenance Export Persistence and Deserialization Test Suite.

Probes multi-workflow history persistence, in-place updates, clean Pydantic
round-trip re-hydration of TaskNode and TaskEdge models, empty workflow handling,
corrupt JSON recovery, and concurrent file export stress.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError
import pytest

from neuri.core.blackboard import (
    Blackboard,
    WorkflowNotFoundError,
)
from neuri.core.schemas import (
    ModalityType,
    NeuriTaskEnvelope,
    RemoteArtifact,
    SanitizedNeuroHeader,
    TaskEdge,
    TaskNode,
    TaskState,
)


@pytest.fixture
def blackboard(tmp_path: Path) -> Blackboard:
    """Provide an initialized Blackboard in a temporary directory.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory.

    Returns
    --------
        Blackboard: Blackboard instance
            Configured SQLite WAL Blackboard instance.
    """
    db_file: Path = tmp_path / "state.db"
    bb: Blackboard = Blackboard(db_file)
    return bb


@pytest.fixture
def sample_header() -> SanitizedNeuroHeader:
    """Provide a validated SanitizedNeuroHeader fixture.

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
def sample_envelope() -> NeuriTaskEnvelope:
    """Provide a validated NeuriTaskEnvelope fixture.

    Parameters
    ------------
    None

    Returns
    --------
        NeuriTaskEnvelope: NeuriTaskEnvelope instance
            Constructed task envelope fixture.
    """
    envelope: NeuriTaskEnvelope = NeuriTaskEnvelope(
        workflow_id="wf-adv-01",
        node_id="node-adv-01",
        agent_role="neuroimaging_specialist",
        harness_id="agy",
        system_prompt="You are a neuroimaging specialist.",
        task_instruction="Preprocess anatomical MRI scan.",
        max_tokens_budget=32000,
        max_cost_usd=1.50,
        attempt_number=1,
        max_retries=2,
    )
    return envelope


class TestAdversarialMultiWorkflowPersistence:
    """Adversarial validation of multi-workflow export and history file persistence."""

    def test_multi_workflow_sequential_export_and_inplace_update(
        self,
        blackboard: Blackboard,
        tmp_path: Path,
    ) -> None:
        """Verify sequential exports produce a root list and update in-place.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        tmp_path: Path
            Pytest temporary directory.

        Returns
        --------
            None: NoneType object
                Asserts export list invariance and in-place replacement.
        """
        history_file: Path = tmp_path / "execution_history.json"

        # Step 1: Export wf-1 to fresh non-existent file
        blackboard.create_workflow("wf-1", "First pipeline run")
        prov_wf1 = blackboard.export_provenance("wf-1", history_file)
        assert prov_wf1["workflow_id"] == "wf-1"

        raw_first: str = history_file.read_text(encoding="utf-8").strip()
        assert raw_first.startswith("["), "Root of exported file must be JSON list"
        assert raw_first.endswith("]"), "Root of exported file must end with ']'"

        data_first: Any = json.loads(raw_first)
        assert isinstance(data_first, list)
        assert len(data_first) == 1
        assert data_first[0]["workflow_id"] == "wf-1"

        # Step 2: Export wf-2 to same file
        blackboard.create_workflow("wf-2", "Second pipeline run")
        prov_wf2 = blackboard.export_provenance("wf-2", history_file)
        assert prov_wf2["workflow_id"] == "wf-2"

        raw_second: str = history_file.read_text(encoding="utf-8").strip()
        data_second: Any = json.loads(raw_second)
        assert isinstance(data_second, list)
        assert len(data_second) == 2

        workflow_ids: list[str] = [entry["workflow_id"] for entry in data_second]
        assert "wf-1" in workflow_ids, "wf-1 must persist after wf-2 export"
        assert "wf-2" in workflow_ids, "wf-2 must be appended to root list"

        # Step 3: Re-export wf-1 with updated data and verify in-place update
        blackboard.update_workflow_status(
            workflow_id="wf-1",
            status="COMPLETED",
            total_tokens=1500,
            estimated_cost_usd=0.045,
        )
        updated_prov_wf1 = blackboard.export_provenance("wf-1", history_file)
        assert updated_prov_wf1["status"] == "COMPLETED"

        raw_third: str = history_file.read_text(encoding="utf-8").strip()
        data_third: Any = json.loads(raw_third)
        assert isinstance(data_third, list)
        assert len(data_third) == 2, "Re-exporting wf-1 must not create duplicates"

        wf1_entry: dict[str, Any] = next(
            e for e in data_third if e["workflow_id"] == "wf-1"
        )
        assert wf1_entry["status"] == "COMPLETED"
        assert wf1_entry["total_tokens"] == 1500
        assert wf1_entry["estimated_cost_usd"] == 0.045

        wf2_entry: dict[str, Any] = next(
            e for e in data_third if e["workflow_id"] == "wf-2"
        )
        assert wf2_entry["workflow_id"] == "wf-2"

    def test_legacy_dict_format_auto_migration(
        self,
        blackboard: Blackboard,
        tmp_path: Path,
    ) -> None:
        """Verify that an existing single-dict JSON file is promoted to list.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        tmp_path: Path
            Pytest temporary directory.

        Returns
        --------
            None: NoneType object
                Asserts legacy dict is promoted into root list without clobbering.
        """
        history_file: Path = tmp_path / "legacy_history.json"
        legacy_dict: dict[str, Any] = {
            "workflow_id": "wf-legacy",
            "prompt": "Old legacy prompt",
            "status": "COMPLETED",
            "total_tokens": 100,
            "estimated_cost_usd": 0.01,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:01:00Z",
            "nodes": [],
            "edges": [],
            "artifacts": [],
            "citations": [],
        }
        history_file.write_text(json.dumps(legacy_dict, indent=2), encoding="utf-8")

        blackboard.create_workflow("wf-new", "Modern workflow")
        blackboard.export_provenance("wf-new", history_file)

        raw_text: str = history_file.read_text(encoding="utf-8").strip()
        data: Any = json.loads(raw_text)
        assert isinstance(data, list)
        assert len(data) == 2
        exported_ids: list[str] = [e["workflow_id"] for e in data]
        assert "wf-legacy" in exported_ids
        assert "wf-new" in exported_ids


class TestAdversarialPydanticRoundTripRehydration:
    """Adversarial stress-tests asserting zero ValidationError on re-hydration."""

    def test_comprehensive_task_nodes_round_trip_rehydration(
        self,
        blackboard: Blackboard,
        sample_envelope: NeuriTaskEnvelope,
        tmp_path: Path,
    ) -> None:
        """Verify that diverse task nodes deserialize cleanly into TaskNode models.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        sample_envelope: NeuriTaskEnvelope
            Task envelope fixture.
        tmp_path: Path
            Pytest temporary directory.

        Returns
        --------
            None: NoneType object
                Asserts all nodes validate cleanly with TaskNode.model_validate.
        """
        history_file: Path = tmp_path / "execution_history.json"
        wf_id: str = "wf-node-rehydration"
        blackboard.create_workflow(wf_id, "Node rehydration workflow")

        # Node 1: Minimal PENDING node (no envelope, no feedback)
        node_1: TaskNode = TaskNode(
            node_id="node-minimal",
            workflow_id=wf_id,
            agent_role="generalist",
            harness_id="codex",
            state=TaskState.PENDING,
        )
        blackboard.create_node(node_1)

        # Node 2: RUNNING node with envelope and attempt count
        env_2: NeuriTaskEnvelope = sample_envelope.model_copy(
            update={"node_id": "node-running", "workflow_id": wf_id}
        )
        node_2: TaskNode = TaskNode(
            node_id="node-running",
            workflow_id=wf_id,
            agent_role="neuroimaging_specialist",
            harness_id="agy",
            state=TaskState.RUNNING,
            attempt=1,
            max_retries=2,
            envelope=env_2,
        )
        blackboard.create_node(node_2)

        # Node 3: COMPLETED node with summary result and feedback
        env_3: NeuriTaskEnvelope = sample_envelope.model_copy(
            update={"node_id": "node-completed", "workflow_id": wf_id}
        )
        node_3: TaskNode = TaskNode(
            node_id="node-completed",
            workflow_id=wf_id,
            agent_role="neuroimaging_specialist",
            harness_id="agy",
            state=TaskState.COMPLETED,
            attempt=1,
            max_retries=2,
            envelope=env_3,
            summary_result="Successfully registered anatomical volume.",
            diagnostic_feedback=["Initial warning: RAS orientation matched."],
        )
        blackboard.create_node(node_3)

        # Node 4: WAITING_OPERATOR node with multi-line diagnostic feedback
        node_4: TaskNode = TaskNode(
            node_id="node-waiting-op",
            workflow_id=wf_id,
            agent_role="operator_liaison",
            harness_id="codex",
            state=TaskState.WAITING_OPERATOR,
            attempt=3,
            max_retries=2,
            diagnostic_feedback=[
                "Fatal tool timeout during FreeSurfer execution",
                "Operator manual intervention required",
            ],
        )
        blackboard.create_node(node_4)

        # Export provenance
        prov: dict[str, Any] = blackboard.export_provenance(wf_id, history_file)
        assert len(prov["nodes"]) == 4

        # Validate that every exported node dict deserializes cleanly
        for node_dict in prov["nodes"]:
            try:
                rehydrated: TaskNode = TaskNode.model_validate(node_dict)
            except ValidationError as exc:
                err_msg = (
                    f"TaskNode.model_validate failed on "
                    f"'{node_dict.get('node_id')}':\n{exc}"
                )
                pytest.fail(err_msg)
            assert rehydrated.workflow_id == wf_id
            assert rehydrated.node_id in {
                "node-minimal",
                "node-running",
                "node-completed",
                "node-waiting-op",
            }
            assert isinstance(rehydrated.state, TaskState)
            assert isinstance(rehydrated.diagnostic_feedback, list)

    def test_comprehensive_task_edges_round_trip_rehydration(
        self,
        blackboard: Blackboard,
        tmp_path: Path,
    ) -> None:
        """Verify that directed edges deserialize cleanly into TaskEdge models.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        tmp_path: Path
            Pytest temporary directory.

        Returns
        --------
            None: NoneType object
                Asserts all edges validate cleanly with TaskEdge.model_validate.
        """
        history_file: Path = tmp_path / "execution_history.json"
        wf_id: str = "wf-edge-rehydration"
        blackboard.create_workflow(wf_id, "Edge rehydration DAG")

        nodes: list[str] = ["node-A", "node-B", "node-C", "node-D"]
        for nid in nodes:
            blackboard.create_node(
                TaskNode(
                    node_id=nid,
                    workflow_id=wf_id,
                    agent_role="specialist",
                    harness_id="agy",
                )
            )

        # Create diamond DAG: A -> B, A -> C, B -> D, C -> D
        edge_pairs: list[tuple[str, str]] = [
            ("node-A", "node-B"),
            ("node-A", "node-C"),
            ("node-B", "node-D"),
            ("node-C", "node-D"),
        ]
        for parent, child in edge_pairs:
            blackboard.add_edge(
                TaskEdge(
                    workflow_id=wf_id,
                    parent_node_id=parent,
                    child_node_id=child,
                )
            )

        prov: dict[str, Any] = blackboard.export_provenance(wf_id, history_file)
        assert len(prov["edges"]) == 4

        for edge_dict in prov["edges"]:
            try:
                rehydrated: TaskEdge = TaskEdge.model_validate(edge_dict)
            except ValidationError as exc:
                pytest.fail(
                    f"TaskEdge.model_validate failed on edge {edge_dict}:\n{exc}"
                )
            assert rehydrated.workflow_id == wf_id
            assert (
                rehydrated.parent_node_id,
                rehydrated.child_node_id,
            ) in edge_pairs


class TestAdversarialProvenanceEdgeCases:
    """Adversarial stress-tests for empty workflows, corruption and concurrency."""

    def test_empty_workflow_provenance_export(
        self,
        blackboard: Blackboard,
        tmp_path: Path,
    ) -> None:
        """Verify exporting an empty workflow succeeds and produces empty collections.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        tmp_path: Path
            Pytest temporary directory.

        Returns
        --------
            None: NoneType object
                Asserts empty collections serialize and validate cleanly.
        """
        history_file: Path = tmp_path / "empty_history.json"
        wf_id: str = "wf-empty-pipeline"
        blackboard.create_workflow(wf_id, "Zero-node empty workflow")

        prov: dict[str, Any] = blackboard.export_provenance(wf_id, history_file)
        assert prov["workflow_id"] == wf_id
        assert prov["nodes"] == []
        assert prov["edges"] == []
        assert prov["artifacts"] == []

        # Trivial re-hydration over empty lists must not fail
        rehydrated_nodes: list[TaskNode] = [
            TaskNode.model_validate(n) for n in prov["nodes"]
        ]
        rehydrated_edges: list[TaskEdge] = [
            TaskEdge.model_validate(e) for e in prov["edges"]
        ]
        assert rehydrated_nodes == []
        assert rehydrated_edges == []

        # File on disk must be a valid JSON list
        raw_text: str = history_file.read_text(encoding="utf-8").strip()
        data: Any = json.loads(raw_text)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["workflow_id"] == wf_id

    def test_corrupt_json_file_recovery_on_export(
        self,
        blackboard: Blackboard,
        tmp_path: Path,
    ) -> None:
        """Verify export recovers from syntax corruption and malformed JSON roots.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        tmp_path: Path
            Pytest temporary directory.

        Returns
        --------
            None: NoneType object
                Asserts corrupted files are overwritten with valid JSON lists.
        """
        history_file: Path = tmp_path / "corrupt_history.json"
        blackboard.create_workflow("wf-recover-1", "Recovery pipeline 1")

        # Scenario 1: Truncated / malformed JSON syntax
        malformed_json: str = (
            '{"workflow_id": "wf-truncated", broken json... ['
        )
        history_file.write_text(malformed_json, encoding="utf-8")
        blackboard.export_provenance("wf-recover-1", history_file)
        raw_1: str = history_file.read_text(encoding="utf-8").strip()
        data_1: Any = json.loads(raw_1)
        assert isinstance(data_1, list)
        assert len(data_1) == 1
        assert data_1[0]["workflow_id"] == "wf-recover-1"

        # Scenario 2: 0-byte empty file
        blackboard.create_workflow("wf-recover-2", "Recovery pipeline 2")
        history_file.write_text("", encoding="utf-8")
        blackboard.export_provenance("wf-recover-2", history_file)
        raw_2: str = history_file.read_text(encoding="utf-8").strip()
        data_2: Any = json.loads(raw_2)
        assert isinstance(data_2, list)
        assert len(data_2) == 1
        assert data_2[0]["workflow_id"] == "wf-recover-2"

        # Scenario 3: Whitespace-only file
        blackboard.create_workflow("wf-recover-3", "Recovery pipeline 3")
        history_file.write_text("   \n\t  \n", encoding="utf-8")
        blackboard.export_provenance("wf-recover-3", history_file)
        raw_3: str = history_file.read_text(encoding="utf-8").strip()
        data_3: Any = json.loads(raw_3)
        assert isinstance(data_3, list)
        assert len(data_3) == 1
        assert data_3[0]["workflow_id"] == "wf-recover-3"

        # Scenario 4: Non-list/dict primitive root (number)
        blackboard.create_workflow("wf-recover-4", "Recovery pipeline 4")
        history_file.write_text("42\n", encoding="utf-8")
        blackboard.export_provenance("wf-recover-4", history_file)
        raw_4: str = history_file.read_text(encoding="utf-8").strip()
        data_4: Any = json.loads(raw_4)
        assert isinstance(data_4, list)
        assert len(data_4) == 1
        assert data_4[0]["workflow_id"] == "wf-recover-4"

        # Scenario 5: List with non-dict elements filtered out
        blackboard.create_workflow("wf-recover-5", "Recovery pipeline 5")
        mixed_list_json: str = (
            '[1, "string", null, {"workflow_id": "wf-recover-4"}]'
        )
        history_file.write_text(mixed_list_json, encoding="utf-8")
        blackboard.export_provenance("wf-recover-5", history_file)
        raw_5: str = history_file.read_text(encoding="utf-8").strip()
        data_5: Any = json.loads(raw_5)
        assert isinstance(data_5, list)
        assert len(data_5) == 2
        exported_ids: list[str] = [e["workflow_id"] for e in data_5]
        assert "wf-recover-4" in exported_ids
        assert "wf-recover-5" in exported_ids

    def test_nonexistent_workflow_raises_error(
        self,
        blackboard: Blackboard,
        tmp_path: Path,
    ) -> None:
        """Verify export_provenance raises WorkflowNotFoundError for unknown IDs.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        tmp_path: Path
            Pytest temporary directory.

        Returns
        --------
            None: NoneType object
                Asserts WorkflowNotFoundError is raised.
        """
        history_file: Path = tmp_path / "execution_history.json"
        with pytest.raises(WorkflowNotFoundError):
            blackboard.export_provenance("wf-does-not-exist", history_file)

    def test_binary_corrupt_file_raises_unicode_decode_error(
        self,
        blackboard: Blackboard,
        tmp_path: Path,
    ) -> None:
        """Document empirical behavior when target file contains non-UTF-8 bytes.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        tmp_path: Path
            Pytest temporary directory.

        Returns
        --------
            None: NoneType object
                Asserts UnicodeDecodeError occurs due to unshielded read_text.
        """
        history_file: Path = tmp_path / "binary_garbage.json"
        history_file.write_bytes(b"\x80\xff\xfe\x00\x01\x99")

        blackboard.create_workflow("wf-binary-corrupt", "Binary corrupt test")
        with pytest.raises(UnicodeDecodeError):
            blackboard.export_provenance("wf-binary-corrupt", history_file)

    def test_concurrent_multi_workflow_export_stress(
        self,
        blackboard: Blackboard,
        tmp_path: Path,
    ) -> None:
        """Stress-test concurrent exports across 8 worker threads.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        tmp_path: Path
            Pytest temporary directory.

        Returns
        --------
            None: NoneType object
                Asserts output file maintains valid JSON structure under concurrency.
        """
        history_file: Path = tmp_path / "concurrent_history.json"
        num_workflows: int = 8
        wf_ids: list[str] = [f"wf-stress-{i}" for i in range(num_workflows)]

        for w_id in wf_ids:
            blackboard.create_workflow(w_id, f"Prompt for {w_id}")
            node_a: TaskNode = TaskNode(
                node_id=f"{w_id}-node-a",
                workflow_id=w_id,
                agent_role="specialist",
                harness_id="agy",
            )
            node_b: TaskNode = TaskNode(
                node_id=f"{w_id}-node-b",
                workflow_id=w_id,
                agent_role="specialist",
                harness_id="agy",
            )
            blackboard.create_node(node_a)
            blackboard.create_node(node_b)
            blackboard.add_edge(
                TaskEdge(
                    workflow_id=w_id,
                    parent_node_id=f"{w_id}-node-a",
                    child_node_id=f"{w_id}-node-b",
                )
            )

        def export_worker(wf_identifier: str) -> None:
            blackboard.export_provenance(wf_identifier, history_file)

        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(export_worker, wf_ids))

        raw_final: str = history_file.read_text(encoding="utf-8").strip()
        data: Any = json.loads(raw_final)
        assert isinstance(data, list)
        assert len(data) > 0

        # Verify that all surviving entries deserialize without ValidationError
        for entry in data:
            for node_dict in entry.get("nodes", []):
                TaskNode.model_validate(node_dict)
            for edge_dict in entry.get("edges", []):
                TaskEdge.model_validate(edge_dict)
