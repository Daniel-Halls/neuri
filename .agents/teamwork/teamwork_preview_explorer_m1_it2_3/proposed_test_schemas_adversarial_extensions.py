"""Proposed adversarial test additions for tests/unit/test_schemas_adversarial.py.

Validates frozen PHI immutability, role/harness contract aliases on TaskNode
and NeuriTaskEnvelope, physical acquisition parameter bounds, NaN rejection,
and cross-field consistency on RemoteArtifact.
"""

import math
from pydantic import ValidationError
import pytest

from neuri.core.schemas import (
    ModalityType,
    NeuriTaskEnvelope,
    NiiVueLayerSpec,
    NiiVueSceneSpec,
    RemoteArtifact,
    SanitizedNeuroHeader,
    TaskNode,
    TaskState,
)


def test_phi_sanitized_post_instantiation_immutability() -> None:
    """Verify SanitizedNeuroHeader is frozen and rejects mutation of PHI flag.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts mutation of phi_sanitized raises ValidationError or TypeError.
    """
    header: SanitizedNeuroHeader = SanitizedNeuroHeader(
        shape=[256, 256, 176],
        dtype="float32",
    )
    with pytest.raises((ValidationError, TypeError)):
        header.phi_sanitized = False  # type: ignore[misc]
    return None


def test_neuri_task_envelope_role_harness_aliases() -> None:
    """Verify NeuriTaskEnvelope accepts role and harness per PROJECT.md line 115.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts alias acceptance and property getter consistency.
    """
    envelope: NeuriTaskEnvelope = NeuriTaskEnvelope(
        workflow_id="wf-001",
        node_id="node-bet-01",
        role="neuroimaging_specialist",
        harness="agy",
        system_prompt="Execute BET brain extraction.",
        task_instruction="Run bet on T1w image.",
    )
    assert envelope.role == "neuroimaging_specialist"
    assert envelope.harness == "agy"
    assert envelope.agent_role == "neuroimaging_specialist"
    assert envelope.harness_id == "agy"
    return None


def test_task_node_role_harness_aliases() -> None:
    """Verify TaskNode accepts role and harness per PROJECT.md line 114.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts alias acceptance and property getter consistency on TaskNode.
    """
    envelope: NeuriTaskEnvelope = NeuriTaskEnvelope(
        workflow_id="wf-001",
        node_id="node-01",
        role="specialist",
        harness="agy",
        system_prompt="sys",
        task_instruction="task",
    )
    node: TaskNode = TaskNode(
        node_id="node-01",
        workflow_id="wf-001",
        role="neuroimaging_specialist",
        harness="agy",
        envelope=envelope,
    )
    assert node.role == "neuroimaging_specialist"
    assert node.harness == "agy"
    assert node.agent_role == "neuroimaging_specialist"
    assert node.harness_id == "agy"
    return None


def test_task_node_diagnostic_feedback_polymorphism() -> None:
    """Verify TaskNode diagnostic_feedback accepts list, string, or None.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts list[str], single string, and None assignment.
    """
    envelope: NeuriTaskEnvelope = NeuriTaskEnvelope(
        workflow_id="wf-001",
        node_id="node-01",
        role="specialist",
        harness="agy",
        system_prompt="sys",
        task_instruction="task",
    )
    node_list: TaskNode = TaskNode(
        node_id="node-01",
        workflow_id="wf-001",
        agent_role="specialist",
        harness_id="agy",
        envelope=envelope,
        diagnostic_feedback=["retry 1 failed", "retry 2 failed"],
    )
    assert len(node_list.diagnostic_feedback) == 2

    node_str: TaskNode = TaskNode(
        node_id="node-02",
        workflow_id="wf-001",
        agent_role="specialist",
        harness_id="agy",
        envelope=envelope,
        diagnostic_feedback="single error string",
    )
    assert node_str.diagnostic_feedback is not None

    node_none: TaskNode = TaskNode(
        node_id="node-03",
        workflow_id="wf-001",
        agent_role="specialist",
        harness_id="agy",
        envelope=envelope,
        diagnostic_feedback=None,
    )
    assert node_none.diagnostic_feedback is None or node_none.diagnostic_feedback == []
    return None


def test_physical_parameters_positive_bounds() -> None:
    """Verify non-positive voxel sizes, TR, sampling rate, and channels fail.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts validation failure on non-positive acquisition parameters.
    """
    with pytest.raises(ValidationError):
        SanitizedNeuroHeader(
            shape=[256, 256, 176],
            dtype="float32",
            voxel_sizes_mm=[-1.0, 1.0, 1.0],
        )

    with pytest.raises(ValidationError):
        SanitizedNeuroHeader(
            shape=[256, 256, 176],
            dtype="float32",
            voxel_sizes_mm=[1.0, 0.0, 1.0],
        )

    with pytest.raises(ValidationError):
        SanitizedNeuroHeader(
            shape=[64, 64, 30, 200],
            dtype="float32",
            tr_seconds=-2.0,
        )

    with pytest.raises(ValidationError):
        SanitizedNeuroHeader(
            shape=[64, 64, 30, 200],
            dtype="float32",
            sampling_freq_hz=0.0,
        )

    with pytest.raises(ValidationError):
        SanitizedNeuroHeader(
            shape=[64, 64, 30, 200],
            dtype="float32",
            channel_count=0,
        )
    return None


def test_nan_in_value_range_rejected() -> None:
    """Verify that IEEE 754 NaN values in value_range are strictly rejected.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts validation failure when min or max intensity is NaN.
    """
    with pytest.raises(ValidationError):
        SanitizedNeuroHeader(
            shape=[10, 10, 10],
            dtype="float32",
            value_range=(float("nan"), 100.0),
        )

    with pytest.raises(ValidationError):
        SanitizedNeuroHeader(
            shape=[10, 10, 10],
            dtype="float32",
            value_range=(0.0, float("nan")),
        )
    return None


def test_remote_artifact_cross_field_consistency() -> None:
    """Verify RemoteArtifact enforces consistency between uri, host, and path.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts validation failure on mismatch between uri and host/path.
    """
    header: SanitizedNeuroHeader = SanitizedNeuroHeader(
        shape=[10, 10, 10],
        dtype="float32",
    )
    with pytest.raises(ValidationError):
        RemoteArtifact(
            artifact_id="art-mismatch",
            uri="clusterA:///scratch/sub-01.nii.gz",
            host="clusterB",
            posix_path="/scratch/sub-01.nii.gz",
            modality=ModalityType.T1W,
            sha256_header="a" * 64,
            size_bytes=1000,
            header_summary=header,
        )
    return None


def test_remote_artifact_posix_path_absolute_enforced() -> None:
    """Verify RemoteArtifact rejects relative posix_path values.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts validation failure when posix_path does not start with '/'.
    """
    header: SanitizedNeuroHeader = SanitizedNeuroHeader(
        shape=[10, 10, 10],
        dtype="float32",
    )
    with pytest.raises(ValidationError):
        RemoteArtifact(
            artifact_id="art-rel",
            uri="localhost:///relative/path.nii.gz",
            host="localhost",
            posix_path="relative/path.nii.gz",
            modality=ModalityType.T1W,
            sha256_header="b" * 64,
            size_bytes=100,
            header_summary=header,
        )
    return None


def test_niivue_scene_spec_requires_non_empty_volumes() -> None:
    """Verify NiiVueSceneSpec requires at least one volume layer.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts validation failure when volumes list is empty.
    """
    with pytest.raises(ValidationError):
        NiiVueSceneSpec(
            scene_id="scene-empty",
            title="Empty Scene",
            volumes=[],
        )
    return None
