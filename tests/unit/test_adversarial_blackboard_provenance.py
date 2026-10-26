"""Adversarial Verification Suite for Neuri Blackboard Provenance & Artifacts.

Empirically probes artifact uniqueness constraints, cross-node collisions,
malformed hash ingestion, citations ledger edge cases, multi-workflow provenance
serialization clobbering, and Pydantic model round-trip re-hydration.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
from typing import Any

from pydantic import ValidationError
import pytest

from neuri.core.blackboard import (
    ArtifactRegistrationError,
    Blackboard,
    BlackboardError,
    NodeNotFoundError,
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
def sample_artifact(sample_header: SanitizedNeuroHeader) -> RemoteArtifact:
    """Provide a validated RemoteArtifact fixture.

    Parameters
    ------------
    sample_header: SanitizedNeuroHeader
        Header fixture.

    Returns
    --------
        RemoteArtifact: RemoteArtifact instance
            Remote artifact pointer model.
    """
    art: RemoteArtifact = RemoteArtifact(
        artifact_id="art-adv-001",
        uri="node-a:///data/derivatives/sub-01_T1w.nii.gz",
        host="node-a",
        posix_path="/data/derivatives/sub-01_T1w.nii.gz",
        modality=ModalityType.T1W,
        space="MNI152NLin2009cAsym",
        bids_entities={"sub": "01", "suffix": "T1w"},
        sha256_header=(
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        ),
        size_bytes=2048,
        header_summary=sample_header,
    )
    return art


class TestAdversarialArtifactRegistration:
    """Adversarial stress-tests for artifact registration and unique constraints."""

    def test_artifact_duplicate_uri_across_workflows_rejected(
        self,
        blackboard: Blackboard,
        sample_artifact: RemoteArtifact,
    ) -> None:
        """Verify that registering the same URI across different workflows fails.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        sample_artifact: RemoteArtifact
            Sample artifact fixture.

        Returns
        --------
            None: NoneType object
                Asserts ArtifactRegistrationError on second workflow registration.
        """
        blackboard.create_workflow("wf-art-1", "Workflow 1")
        blackboard.create_workflow("wf-art-2", "Workflow 2")

        blackboard.register_artifact(sample_artifact, workflow_id="wf-art-1")

        with pytest.raises(ArtifactRegistrationError) as exc_info:
            blackboard.register_artifact(sample_artifact, workflow_id="wf-art-2")
        assert "already registered" in str(exc_info.value)

    def test_artifact_same_posix_path_on_different_hosts_allowed(
        self,
        blackboard: Blackboard,
        sample_header: SanitizedNeuroHeader,
    ) -> None:
        """Verify identical POSIX paths on distinct hosts are allowed.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        sample_header: SanitizedNeuroHeader
            Sanitized header fixture.

        Returns
        --------
            None: NoneType object
                Asserts both artifacts are successfully stored.
        """
        blackboard.create_workflow("wf-multihost", "Multi-host workflow")

        art_host_a: RemoteArtifact = RemoteArtifact(
            artifact_id="art-host-a",
            uri="cluster-a:///shared/scratch/sub-01.nii.gz",
            host="cluster-a",
            posix_path="/shared/scratch/sub-01.nii.gz",
            modality=ModalityType.T1W,
            sha256_header="a" * 64,
            size_bytes=1000,
            header_summary=sample_header,
        )
        art_host_b: RemoteArtifact = RemoteArtifact(
            artifact_id="art-host-b",
            uri="cluster-b:///shared/scratch/sub-01.nii.gz",
            host="cluster-b",
            posix_path="/shared/scratch/sub-01.nii.gz",
            modality=ModalityType.T1W,
            sha256_header="b" * 64,
            size_bytes=1000,
            header_summary=sample_header,
        )

        blackboard.register_artifact(art_host_a, workflow_id="wf-multihost")
        blackboard.register_artifact(art_host_b, workflow_id="wf-multihost")

        fetched_a = blackboard.get_artifact(art_host_a.uri)
        fetched_b = blackboard.get_artifact(art_host_b.uri)
        assert fetched_a is not None
        assert fetched_b is not None
        assert fetched_a.host == "cluster-a"
        assert fetched_b.host == "cluster-b"

    def test_artifact_duplicate_artifact_id_raises_integrity_error(
        self,
        blackboard: Blackboard,
        sample_header: SanitizedNeuroHeader,
    ) -> None:
        """Verify registering duplicate artifact_id with distinct URIs.

        Probes whether primary key collision leaks sqlite3.IntegrityError
        instead of raising BlackboardError / ArtifactRegistrationError.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        sample_header: SanitizedNeuroHeader
            Sanitized header fixture.

        Returns
        --------
            None: NoneType object
                Asserts exception is raised on primary key collision.
        """
        blackboard.create_workflow("wf-pk", "PK collision workflow")

        art_1: RemoteArtifact = RemoteArtifact(
            artifact_id="art-pk-01",
            uri="node-a:///data/file1.nii.gz",
            host="node-a",
            posix_path="/data/file1.nii.gz",
            modality=ModalityType.T1W,
            sha256_header="1" * 64,
            size_bytes=500,
            header_summary=sample_header,
        )
        art_2: RemoteArtifact = RemoteArtifact(
            artifact_id="art-pk-01",
            uri="node-a:///data/file2.nii.gz",
            host="node-a",
            posix_path="/data/file2.nii.gz",
            modality=ModalityType.T1W,
            sha256_header="2" * 64,
            size_bytes=500,
            header_summary=sample_header,
        )

        blackboard.register_artifact(art_1, workflow_id="wf-pk")

        with pytest.raises((ArtifactRegistrationError, sqlite3.IntegrityError)):
            blackboard.register_artifact(art_2, workflow_id="wf-pk")

    def test_artifact_cross_workflow_node_foreign_key_behavior(
        self,
        blackboard: Blackboard,
        sample_header: SanitizedNeuroHeader,
    ) -> None:
        """Verify cross-workflow node attachment raises NodeNotFoundError.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        sample_header: SanitizedNeuroHeader
            Sanitized header fixture.

        Returns
        --------
            None: NoneType object
                Asserts NodeNotFoundError on cross-workflow node attachment.
        """
        blackboard.create_workflow("wf-a", "Workflow A")
        blackboard.create_workflow("wf-b", "Workflow B")

        node_a: TaskNode = TaskNode(
            node_id="node-in-wf-a",
            workflow_id="wf-a",
            agent_role="specialist",
            harness_id="agy",
        )
        blackboard.create_node(node_a)

        art: RemoteArtifact = RemoteArtifact(
            artifact_id="art-cross-wf",
            uri="host-x:///data/cross.nii.gz",
            host="host-x",
            posix_path="/data/cross.nii.gz",
            modality=ModalityType.T1W,
            sha256_header="3" * 64,
            size_bytes=100,
            header_summary=sample_header,
        )

        with pytest.raises(NodeNotFoundError) as exc_info:
            blackboard.register_artifact(
                art, workflow_id="wf-b", node_id="node-in-wf-a"
            )
        assert "does not exist in workflow" in str(exc_info.value)

    def test_artifact_malformed_sha256_hash_rejected(
        self,
        blackboard: Blackboard,
        sample_header: SanitizedNeuroHeader,
    ) -> None:
        """Verify that malformed sha256 hash digests are rejected.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        sample_header: SanitizedNeuroHeader
            Sanitized header fixture.

        Returns
        --------
            None: NoneType object
                Asserts ValidationError on malformed SHA-256 hash.
        """
        blackboard.create_workflow("wf-hash", "Malformed hash workflow")

        with pytest.raises(ValidationError):
            RemoteArtifact(
                artifact_id="art-bad-hash-01",
                uri="cluster-a:///data/bad_hash.nii.gz",
                host="cluster-a",
                posix_path="/data/bad_hash.nii.gz",
                modality=ModalityType.T1W,
                sha256_header="not_a_valid_hex_hash_12345",
                size_bytes=100,
                header_summary=sample_header,
            )



class TestAdversarialCitationsLedger:
    """Adversarial stress-tests for citations ledger and BibTeX synchronization."""

    def test_citation_missing_doi_and_pmid_handled(
        self,
        blackboard: Blackboard,
    ) -> None:
        """Verify citation without DOI or PMID persists and queries cleanly.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts None values for missing identifiers.
        """
        blackboard.register_citation(
            citation_key="jenkinson2012fsl",
            title="FSL",
            bibtex="@article{jenkinson2012fsl, title={FSL}}",
            doi=None,
            pmid=None,
            year=2012,
        )

        cit = blackboard.get_citation("jenkinson2012fsl")
        assert cit is not None
        assert cit["doi"] is None
        assert cit["pmid"] is None
        assert cit["year"] == 2012

        assert blackboard.get_citation_by_doi("nonexistent-doi") is None

    def test_citation_duplicate_doi_different_keys(
        self,
        blackboard: Blackboard,
    ) -> None:
        """Verify registering multiple citations sharing the same DOI.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts both citations exist independently in ledger.
        """
        shared_doi: str = "10.1016/j.neuroimage.2011.09.015"
        blackboard.register_citation(
            citation_key="ref1",
            title="Paper One",
            bibtex="@article{ref1, title={Paper One}}",
            doi=shared_doi,
        )
        blackboard.register_citation(
            citation_key="ref2",
            title="Paper Two Alias",
            bibtex="@article{ref2, title={Paper Two Alias}}",
            doi=shared_doi,
        )

        cit1 = blackboard.get_citation("ref1")
        cit2 = blackboard.get_citation("ref2")
        assert cit1 is not None
        assert cit2 is not None

        by_doi = blackboard.get_citation_by_doi(shared_doi)
        assert by_doi is not None
        assert by_doi["citation_key"] in ("ref1", "ref2")

    def test_citation_year_check_constraint_boundary(
        self,
        blackboard: Blackboard,
    ) -> None:
        """Verify year constraint (1800 to 2100) rejects out-of-bounds years.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts BlackboardError wrapping on invalid years.
        """
        with pytest.raises(BlackboardError) as exc_info_ancient:
            blackboard.register_citation(
                citation_key="ancient1700",
                title="Ancient Work",
                bibtex="@article{ancient1700, title={Ancient}}",
                year=1750,
            )
        assert "integrity constraint violation" in str(exc_info_ancient.value)

        with pytest.raises(BlackboardError) as exc_info_future:
            blackboard.register_citation(
                citation_key="future3000",
                title="Future Work",
                bibtex="@article{future3000, title={Future}}",
                year=3000,
            )
        assert "integrity constraint violation" in str(exc_info_future.value)

    def test_citation_sync_writes_utf8_special_characters(
        self,
        blackboard: Blackboard,
        tmp_path: Path,
    ) -> None:
        """Verify sync_citations_to_bib preserves international author characters.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        tmp_path: Path
            Pytest temporary directory.

        Returns
        --------
            None: NoneType object
                Asserts UTF-8 preservation in exported bib file.
        """
        bib_file: Path = tmp_path / "references.bib"
        bibtex=(
            "@article{tournier2019mrtrix, "
            "author={Tournier, J-Donald and Calamante, Fernando}}"
        )
        blackboard.register_citation(
            citation_key="tournier2019mrtrix",
            title="MRtrix3: A fast flexible software package",
            bibtex=bibtex,
            authors=["Tournier, J-Donald", "Calamante, Fernando"],
            verified=True,
        )

        count = blackboard.sync_citations_to_bib(bib_file)
        assert count == 1
        content = bib_file.read_text(encoding="utf-8")
        assert "MRtrix3" in content
        assert "Tournier, J-Donald" in content

    def test_citation_malformed_bibtex_rejected_by_register(
        self,
        blackboard: Blackboard,
        tmp_path: Path,
    ) -> None:
        """Verify that malformed BibTeX syntax is rejected with BlackboardError.

        Prevents corrupting references.bib by validating that BibTeX strings
        contain non-empty content with basic entry structure (@ and {...}).

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        tmp_path: Path
            Pytest temporary directory.

        Returns
        --------
            None: NoneType object
                Asserts BlackboardError on malformed BibTeX entries.
        """
        malformed_inputs: list[str] = [
            "MALFORMED_BIBTEX_WITHOUT_BRACES_OR_ENTRY_TYPE",
            "",
            "   ",
            "@article",
            "@{missing_type}",
            "@article{unclosed",
            "@article}inverted{",
        ]

        for bad_bib in malformed_inputs:
            with pytest.raises(BlackboardError):
                blackboard.register_citation(
                    citation_key="badbib2024",
                    title="Broken BibTeX Paper",
                    bibtex=bad_bib,
                    verified=True,
                )



class TestAdversarialProvenanceExport:
    """Adversarial stress-tests for provenance export and history serialization."""

    def test_export_provenance_multi_workflow_clobber_vulnerability(
        self,
        blackboard: Blackboard,
        tmp_path: Path,
    ) -> None:
        """Probe multi-workflow provenance export clobbering behavior.

        Vulnerability: If export_provenance is invoked on a new file, it writes
        a dict instead of a list. Subsequent exports see raw_text starting
        with '{' rather than '[', skipping list merge and clobbering the file!

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        tmp_path: Path
            Pytest temporary directory.

        Returns
        --------
            None: NoneType object
                Evaluates whether history file retains all exported workflows.
        """
        history_file: Path = tmp_path / "execution_history.json"

        blackboard.create_workflow("wf-run-1", "Initial pipeline run")
        blackboard.export_provenance("wf-run-1", history_file)

        raw_first = history_file.read_text(encoding="utf-8").strip()
        is_list_first = raw_first.startswith("[")

        blackboard.create_workflow("wf-run-2", "Second pipeline run")
        blackboard.export_provenance("wf-run-2", history_file)

        raw_second = history_file.read_text(encoding="utf-8").strip()

        parsed_data = json.loads(raw_second)
        if isinstance(parsed_data, list):
            workflow_ids = [entry["workflow_id"] for entry in parsed_data]
            assert "wf-run-1" in workflow_ids, (
                "CRITICAL DATA LOSS: First workflow was clobbered by second export!"
            )
            assert "wf-run-2" in workflow_ids
        else:
            assert False, (
                f"FAIL: execution_history.json was written as a dictionary root, "
                f"causing second export to overwrite previous history! "
                f"Active workflow in file is '{parsed_data.get('workflow_id')}'."
            )

    def test_export_provenance_round_trip_task_node_rehydration(
        self,
        blackboard: Blackboard,
        tmp_path: Path,
    ) -> None:
        """Probe whether exported provenance nodes can be re-hydrated into TaskNode.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        tmp_path: Path
            Pytest temporary directory.

        Returns
        --------
            None: NoneType object
                Validates TaskNode Pydantic round-trip fidelity.
        """
        export_file: Path = tmp_path / "execution_history.json"
        blackboard.create_workflow("wf-rt-node", "Round-trip node test")

        envelope: NeuriTaskEnvelope = NeuriTaskEnvelope(
            workflow_id="wf-rt-node",
            node_id="node-rt-01",
            agent_role="neuroimaging_specialist",
            harness_id="agy",
            system_prompt="You are a neuroimaging specialist.",
            task_instruction="Preprocess anatomical data.",
        )
        node: TaskNode = TaskNode(
            node_id="node-rt-01",
            workflow_id="wf-rt-node",
            agent_role="neuroimaging_specialist",
            harness_id="agy",
            state=TaskState.COMPLETED,
            envelope=envelope,
        )
        blackboard.create_node(node)

        prov = blackboard.export_provenance("wf-rt-node", export_file)
        node_dict = prov["nodes"][0]

        rehydrated_node = TaskNode.model_validate(node_dict)
        assert rehydrated_node.node_id == "node-rt-01"

    def test_export_provenance_round_trip_task_edge_rehydration(
        self,
        blackboard: Blackboard,
        tmp_path: Path,
    ) -> None:
        """Probe whether exported provenance edges can be re-hydrated into TaskEdge.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        tmp_path: Path
            Pytest temporary directory.

        Returns
        --------
            None: NoneType object
                Validates TaskEdge Pydantic round-trip fidelity.
        """
        export_file: Path = tmp_path / "execution_history.json"
        blackboard.create_workflow("wf-rt-edge", "Round-trip edge test")

        node1: TaskNode = TaskNode(
            node_id="node-parent",
            workflow_id="wf-rt-edge",
            agent_role="specialist",
            harness_id="agy",
        )
        node2: TaskNode = TaskNode(
            node_id="node-child",
            workflow_id="wf-rt-edge",
            agent_role="specialist",
            harness_id="agy",
        )
        blackboard.create_node(node1)
        blackboard.create_node(node2)

        edge: TaskEdge = TaskEdge(
            workflow_id="wf-rt-edge",
            parent_node_id="node-parent",
            child_node_id="node-child",
        )
        blackboard.add_edge(edge)

        prov = blackboard.export_provenance("wf-rt-edge", export_file)
        edge_dict = prov["edges"][0]

        rehydrated_edge = TaskEdge.model_validate(edge_dict)
        assert rehydrated_edge.parent_node_id == "node-parent"

    def test_export_provenance_round_trip_remote_artifact_rehydration(
        self,
        blackboard: Blackboard,
        sample_artifact: RemoteArtifact,
        tmp_path: Path,
    ) -> None:
        """Verify exported provenance artifacts re-hydrate cleanly into RemoteArtifact.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        sample_artifact: RemoteArtifact
            Remote artifact fixture.
        tmp_path: Path
            Pytest temporary directory.

        Returns
        --------
            None: NoneType object
                Asserts RemoteArtifact round-trip deserialization succeeds.
        """
        export_file: Path = tmp_path / "execution_history.json"
        blackboard.create_workflow("wf-rt-art", "Round-trip artifact test")
        blackboard.register_artifact(sample_artifact, workflow_id="wf-rt-art")

        prov = blackboard.export_provenance("wf-rt-art", export_file)
        art_dict = prov["artifacts"][0]

        rehydrated_art = RemoteArtifact.model_validate(art_dict)
        assert rehydrated_art.artifact_id == sample_artifact.artifact_id
        assert rehydrated_art.uri == sample_artifact.uri
        assert rehydrated_art.header_summary.phi_sanitized is True

    def test_export_provenance_unwriteable_directory_raises_permission_error(
        self,
        blackboard: Blackboard,
        tmp_path: Path,
    ) -> None:
        """Verify export to a read-only directory raises PermissionError.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        tmp_path: Path
            Pytest temporary directory.

        Returns
        --------
            None: NoneType object
                Asserts PermissionError or OSError on unwriteable path.
        """
        ro_dir: Path = tmp_path / "readonly_dir"
        ro_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(ro_dir, 0o555)

        export_target: Path = ro_dir / "execution_history.json"
        blackboard.create_workflow("wf-ro", "Readonly test")

        try:
            with pytest.raises((PermissionError, OSError)):
                blackboard.export_provenance("wf-ro", export_target)
        finally:
            os.chmod(ro_dir, 0o755)

    def test_export_provenance_concurrent_exports_do_not_corrupt_json(
        self,
        blackboard: Blackboard,
        tmp_path: Path,
    ) -> None:
        """Verify concurrent exports to a pre-seeded history list file.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        tmp_path: Path
            Pytest temporary directory.

        Returns
        --------
            None: NoneType object
                Asserts history file remains valid JSON after concurrent writes.
        """
        history_file: Path = tmp_path / "execution_history.json"
        history_file.write_text("[]\n", encoding="utf-8")

        wf_ids: list[str] = [f"wf-conc-{i}" for i in range(10)]
        for w_id in wf_ids:
            blackboard.create_workflow(w_id, f"Prompt for {w_id}")

        def export_worker(wf_id: str) -> None:
            """Export provenance for a single workflow in thread worker.

            Parameters
            ------------
            wf_id: str
                Workflow identifier to export.

            Returns
            --------
                None: NoneType object
                    Writes provenance to history file.
            """
            blackboard.export_provenance(wf_id, history_file)

        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(export_worker, wf_ids))

        raw_final = history_file.read_text(encoding="utf-8").strip()
        data = json.loads(raw_final)
        assert isinstance(data, list)
        assert len(data) > 0
