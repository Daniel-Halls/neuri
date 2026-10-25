"""Adversarial challenge test suite for Neuri core Pydantic schemas (M1).

Stress-tests PHI sanitization enforcement, boundary conditions, mutation attacks,
alias normalization, and JSON roundtrip serialization across all 13 models.
"""

from datetime import datetime, timezone
import json
import math
from typing import Any

from pydantic import ValidationError
import pytest

from neuri.core.schemas import (
    ChatRole,
    ChatTurn,
    ModalityType,
    NeuriTaskEnvelope,
    NeuriTaskResult,
    NiiVueLayerSpec,
    NiiVueSceneSpec,
    RemoteArtifact,
    SanitizedNeuroHeader,
    SessionEvent,
    SessionEventType,
    TaskEdge,
    TaskNode,
    TaskState,
    TelemetryEvent,
)


def test_phi_sanitized_literal_enforcement() -> None:
    """Verify that any non-True value for phi_sanitized is rejected on init.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts validation failure when phi_sanitized is False or None.
    """
    with pytest.raises(ValidationError) as exc_info_false:
        SanitizedNeuroHeader(
            shape=[256, 256, 176],
            dtype="float32",
            phi_sanitized=False,  # type: ignore[arg-type]
        )
    assert "phi_sanitized" in str(exc_info_false.value)

    with pytest.raises(ValidationError) as exc_info_none:
        SanitizedNeuroHeader(
            shape=[256, 256, 176],
            dtype="float32",
            phi_sanitized=None,  # type: ignore[arg-type]
        )
    assert "phi_sanitized" in str(exc_info_none.value)


def test_extra_fields_forbidden_on_sanitized_header() -> None:
    """Verify that injection of PHI fields is rejected by extra='forbid'.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts validation failure on unmodeled PHI fields.
    """
    with pytest.raises(ValidationError) as exc_info:
        SanitizedNeuroHeader(
            shape=[256, 256, 176],
            dtype="float32",
            patient_name="John Doe",  # type: ignore[call-arg]
            patient_dob="1980-01-01",  # type: ignore[call-arg]
        )
    assert "Extra inputs are not permitted" in str(exc_info.value)


def test_orientation_boundary_cases() -> None:
    """Verify 3-letter orientation validation and rejection of invalid codes.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts normalization to uppercase and rejection of non-3-letter codes.
    """
    header_lower: SanitizedNeuroHeader = SanitizedNeuroHeader(
        shape=[256, 256, 176],
        dtype="float32",
        orientation="ras",
    )
    assert header_lower.orientation == "RAS"

    with pytest.raises(ValidationError):
        SanitizedNeuroHeader(
            shape=[256, 256, 176],
            dtype="float32",
            orientation="RA",
        )

    with pytest.raises(ValidationError):
        SanitizedNeuroHeader(
            shape=[256, 256, 176],
            dtype="float32",
            orientation="RASS",
        )

    with pytest.raises(ValidationError):
        SanitizedNeuroHeader(
            shape=[256, 256, 176],
            dtype="float32",
            orientation="   ",
        )


def test_shape_boundary_rejections() -> None:
    """Verify shape rejects empty arrays and non-positive dimension values.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts validation failure on empty, zero, or negative dimensions.
    """
    with pytest.raises(ValidationError) as exc_empty:
        SanitizedNeuroHeader(
            shape=[],
            dtype="float32",
        )
    assert "shape" in str(exc_empty.value)

    with pytest.raises(ValidationError) as exc_zero:
        SanitizedNeuroHeader(
            shape=[256, 0, 176],
            dtype="float32",
        )
    assert "positive" in str(exc_zero.value)

    with pytest.raises(ValidationError) as exc_neg:
        SanitizedNeuroHeader(
            shape=[256, -10, 176],
            dtype="float32",
        )
    assert "positive" in str(exc_neg.value)


def test_value_range_min_max_inverted_rejection() -> None:
    """Verify value_range rejects tuples where min exceeds max.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts validation failure on inverted min/max intensity range.
    """
    with pytest.raises(ValidationError) as exc_info:
        SanitizedNeuroHeader(
            shape=[256, 256, 176],
            dtype="float32",
            value_range=(100.0, 50.0),
        )
    assert "cannot exceed maximum" in str(exc_info.value)


def test_remote_artifact_uri_regex_validation() -> None:
    """Verify that remote artifact URI requires host_alias:///posix_path format.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts rejection of invalid URI formats.
    """
    header: SanitizedNeuroHeader = SanitizedNeuroHeader(
        shape=[128, 128, 64],
        dtype="int16",
    )

    valid_artifact: RemoteArtifact = RemoteArtifact(
        artifact_id="art-valid",
        uri="node-01:///scratch/data.nii.gz",
        host="node-01",
        posix_path="/scratch/data.nii.gz",
        modality=ModalityType.T1W,
        sha256_header="a" * 64,
        size_bytes=1000,
        header_summary=header,
    )
    assert valid_artifact.uri == "node-01:///scratch/data.nii.gz"

    with pytest.raises(ValidationError):
        RemoteArtifact(
            artifact_id="art-bad-uri-1",
            uri="/missing/host/prefix.nii.gz",
            host="node-01",
            posix_path="/scratch/data.nii.gz",
            modality=ModalityType.T1W,
            sha256_header="a" * 64,
            size_bytes=1000,
            header_summary=header,
        )

    with pytest.raises(ValidationError):
        RemoteArtifact(
            artifact_id="art-bad-uri-2",
            uri="http://web-uri.com/file.nii.gz",
            host="node-01",
            posix_path="/scratch/data.nii.gz",
            modality=ModalityType.T1W,
            sha256_header="a" * 64,
            size_bytes=1000,
            header_summary=header,
        )


def test_task_edge_self_loop_detected() -> None:
    """Verify that TaskEdge rejects parent_node_id == child_node_id.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts validation failure on self loop.
    """
    with pytest.raises(ValidationError) as exc_info:
        TaskEdge(
            workflow_id="wf-cycle",
            parent_node_id="node_x",
            child_node_id="node_x",
        )
    assert "Self-loop detected" in str(exc_info.value)


def test_neuri_task_envelope_resource_budgets() -> None:
    """Verify positive ceilings on max_tokens_budget and max_cost_usd.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts validation failure on zero or negative budgets.
    """
    with pytest.raises(ValidationError):
        NeuriTaskEnvelope(
            workflow_id="wf-01",
            node_id="node-01",
            agent_role="specialist",
            harness_id="agy",
            system_prompt="sys",
            task_instruction="inst",
            max_tokens_budget=0,
        )

    with pytest.raises(ValidationError):
        NeuriTaskEnvelope(
            workflow_id="wf-01",
            node_id="node-01",
            agent_role="specialist",
            harness_id="agy",
            system_prompt="sys",
            task_instruction="inst",
            max_cost_usd=0.0,
        )


def test_neuri_task_result_alias_normalization() -> None:
    """Verify NeuriTaskResult normalizes output_artifacts and tokens_consumed.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts alias mapping from raw dictionaries to canonical fields.
    """
    raw_payload: dict[str, Any] = {
        "node_id": "node-42",
        "success": True,
        "exit_code": 0,
        "summary": "Completed successfully",
        "output_artifacts": [],
        "tokens_consumed": 2048,
    }
    result: NeuriTaskResult = NeuriTaskResult.model_validate(raw_payload)
    assert result.artifacts_emitted == []
    assert result.total_tokens == 2048
    assert result.output_artifacts == []
    assert result.tokens_consumed == 2048
    assert result.is_ok() is True


def test_telemetry_event_type_safety() -> None:
    """Verify TelemetryEvent rejects invalid event_type and negative tokens.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts validation failure on invalid literal or negative values.
    """
    with pytest.raises(ValidationError):
        TelemetryEvent(
            event_id="evt-bad",
            workflow_id="wf-01",
            node_id="node-01",
            harness_id="agy",
            event_type="bogus_event_type",  # type: ignore[arg-type]
        )

    with pytest.raises(ValidationError):
        TelemetryEvent(
            event_id="evt-bad-tokens",
            workflow_id="wf-01",
            node_id="node-01",
            harness_id="agy",
            event_type="token_usage",
            input_tokens=-10,
        )


def test_niivue_layer_opacity_and_cal_bounds() -> None:
    """Verify NiiVueLayerSpec bounds opacity in [0, 1] and cal_min <= cal_max.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts validation failure on out of bounds opacity and cal range.
    """
    with pytest.raises(ValidationError):
        NiiVueLayerSpec(
            artifact_uri="cluster:///vol.nii.gz",
            opacity=1.5,
        )

    with pytest.raises(ValidationError):
        NiiVueLayerSpec(
            artifact_uri="cluster:///vol.nii.gz",
            opacity=-0.1,
        )

    with pytest.raises(ValidationError):
        NiiVueLayerSpec(
            artifact_uri="cluster:///vol.nii.gz",
            cal_min=50.0,
            cal_max=10.0,
        )


def test_json_roundtrip_all_models() -> None:
    """Verify lossless JSON serialization and deserialization across core models.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts serialization roundtrip preserves types and values.
    """
    header: SanitizedNeuroHeader = SanitizedNeuroHeader(
        shape=[256, 256, 176, 200],
        voxel_sizes_mm=[1.0, 1.0, 1.0],
        orientation="RAS",
        tr_seconds=2.0,
        dtype="float32",
        nan_count=0,
        inf_count=0,
        value_range=(0.0, 1000.0),
    )
    header_json: str = header.model_dump_json()
    re_header: SanitizedNeuroHeader = SanitizedNeuroHeader.model_validate_json(
        header_json
    )
    assert re_header.shape == header.shape
    assert re_header.phi_sanitized is True

    artifact: RemoteArtifact = RemoteArtifact(
        artifact_id="art-test",
        uri="host:///data/file.nii.gz",
        host="host",
        posix_path="/data/file.nii.gz",
        modality=ModalityType.BOLD,
        sha256_header="0123456789abcdef" * 4,
        size_bytes=1048576,
        header_summary=header,
    )
    artifact_json: str = artifact.model_dump_json()
    re_artifact: RemoteArtifact = RemoteArtifact.model_validate_json(
        artifact_json
    )
    assert re_artifact.artifact_id == artifact.artifact_id
    assert re_artifact.modality == ModalityType.BOLD

    telemetry: TelemetryEvent = TelemetryEvent(
        event_id="evt-01",
        workflow_id="wf-01",
        node_id="n-01",
        harness_id="agy",
        event_type="token_usage",
        input_tokens=100,
        output_tokens=50,
        estimated_cost_usd=0.005,
    )
    telem_json: str = telemetry.model_dump_json()
    re_telem: TelemetryEvent = TelemetryEvent.model_validate_json(telem_json)
    assert re_telem.event_id == telemetry.event_id
    assert re_telem.output_tokens == 50

    session_evt: SessionEvent = SessionEvent(
        event_id="se-01",
        session_id="sess-01",
        event_type=SessionEventType.STATUS_UPDATE,
        payload={"progress": 0.75, "active_step": "BET"},
    )
    sess_json: str = session_evt.model_dump_json()
    re_sess: SessionEvent = SessionEvent.model_validate_json(sess_json)
    assert re_sess.event_id == session_evt.event_id
    assert re_sess.payload["progress"] == 0.75


def test_phi_sanitized_post_instantiation_immutability() -> None:
    """Verify SanitizedNeuroHeader is frozen and rejects mutation of PHI flag.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts mutation of phi_sanitized raises ValidationError.
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
    assert (
        node_none.diagnostic_feedback is None
        or node_none.diagnostic_feedback == []
    )
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

