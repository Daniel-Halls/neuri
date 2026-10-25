"""Unit tests for Neuri core Pydantic schemas (M1).

Verifies strict validation, data contracts, and edge cases across all 13 core models:
ModalityType, SanitizedNeuroHeader, RemoteArtifact, TaskState, TaskNode,
TaskEdge, NeuriTaskEnvelope, NeuriTaskResult, TelemetryEvent, NiiVueLayerSpec,
NiiVueSceneSpec, ChatRole, ChatTurn, and SessionEvent.
"""

from datetime import datetime
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


def test_modality_type_enum_members() -> None:
    """Verify all 12 supported neuroscience data modalities are defined.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts that all 12 modality enum members exist and match values.
    """
    expected_modalities: dict[str, ModalityType] = {
        "T1w": ModalityType.T1W,
        "T2w": ModalityType.T2W,
        "bold": ModalityType.BOLD,
        "dwi": ModalityType.DWI,
        "tractography": ModalityType.TRACTOGRAPHY,
        "surface": ModalityType.SURFACE,
        "eeg": ModalityType.EEG,
        "meg": ModalityType.MEG,
        "ieeg": ModalityType.IEEG,
        "posterior": ModalityType.POSTERIOR,
        "table": ModalityType.TABLE,
        "report_qa": ModalityType.REPORT_QA,
    }
    assert len(ModalityType) == 12
    for raw_str, enum_val in expected_modalities.items():
        assert enum_val.value == raw_str
        assert ModalityType(raw_str) == enum_val


def test_modality_type_invalid_value() -> None:
    """Verify that unsupported modality strings raise a ValueError.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts that invalid modality raises ValueError.
    """
    with pytest.raises(ValueError):
        ModalityType("invalid_modality_xyz")


def test_sanitized_neuro_header_valid() -> None:
    """Verify valid SanitizedNeuroHeader instantiation and default phi_sanitized.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts valid instantiation of structural neuro metadata.
    """
    header: SanitizedNeuroHeader = SanitizedNeuroHeader(
        shape=[256, 256, 176],
        voxel_sizes_mm=[1.0, 1.0, 1.0],
        orientation="RAS",
        tr_seconds=2.0,
        dtype="float32",
        nan_count=0,
        inf_count=0,
        value_range=(0.0, 255.0),
    )
    assert header.shape == [256, 256, 176]
    assert header.voxel_sizes_mm == [1.0, 1.0, 1.0]
    assert header.orientation == "RAS"
    assert header.phi_sanitized is True


def test_sanitized_neuro_header_phi_sanitized_false_rejected() -> None:
    """CRITICAL: Verify that phi_sanitized=False raises a ValidationError.

    Ensures that un-anonymized headers can never be constructed or passed
    into LLM context windows.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts that phi_sanitized=False triggers validation failure.
    """
    with pytest.raises(ValidationError) as exc_info:
        SanitizedNeuroHeader(
            shape=[256, 256, 176],
            dtype="float32",
            phi_sanitized=False,  # type: ignore[arg-type]
        )
    assert "phi_sanitized" in str(exc_info.value)


def test_sanitized_neuro_header_missing_required_fields() -> None:
    """Verify that omitting required fields (shape, dtype) raises ValidationError.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts validation failure on missing required fields.
    """
    with pytest.raises(ValidationError):
        SanitizedNeuroHeader()  # type: ignore[call-arg]


def test_remote_artifact_valid() -> None:
    """Verify valid RemoteArtifact construction and property access.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts valid artifact construction.
    """
    header: SanitizedNeuroHeader = SanitizedNeuroHeader(
        shape=[128, 128, 64],
        dtype="int16",
        orientation="LPS",
    )
    artifact: RemoteArtifact = RemoteArtifact(
        artifact_id="art-001",
        uri="hpc-cluster:///scratch/neuro/sub-01_T1w.nii.gz",
        host="hpc-cluster",
        posix_path="/scratch/neuro/sub-01_T1w.nii.gz",
        modality=ModalityType.T1W,
        space="native",
        bids_entities={"sub": "01", "datatype": "anat", "suffix": "T1w"},
        sha256_header="a1b2c3d4e5f67890" * 4,
        size_bytes=1048576,
        header_summary=header,
    )
    assert artifact.artifact_id == "art-001"
    assert artifact.host == "hpc-cluster"
    assert artifact.modality == ModalityType.T1W
    assert artifact.header_summary.phi_sanitized is True
    assert artifact.created_by_node is None
    assert isinstance(artifact.created_at, datetime)


def test_remote_artifact_serialization_roundtrip() -> None:
    """Verify RemoteArtifact model_dump and model_validate round-trip integrity.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts serialization and deserialization match original model.
    """
    header: SanitizedNeuroHeader = SanitizedNeuroHeader(
        shape=[64, 1000],
        dtype="float32",
        channel_count=64,
    )
    original: RemoteArtifact = RemoteArtifact(
        artifact_id="art-eeg-01",
        uri="local:///data/eeg/sub-02_task-rest_eeg.fif",
        host="local",
        posix_path="/data/eeg/sub-02_task-rest_eeg.fif",
        modality=ModalityType.EEG,
        sha256_header="e3b0c44298fc1c14" * 4,
        size_bytes=524288,
        header_summary=header,
    )
    dumped: dict[str, Any] = original.model_dump()
    reconstituted: RemoteArtifact = RemoteArtifact.model_validate(dumped)
    assert reconstituted.artifact_id == original.artifact_id
    assert reconstituted.modality == original.modality
    assert reconstituted.header_summary.shape == [64, 1000]


def test_task_state_lifecycle_members() -> None:
    """Verify all 9 task lifecycle states exist in TaskState enum.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts existence of all 9 DAG node lifecycle states.
    """
    expected_states: set[str] = {
        "PENDING",
        "PREFLIGHT_CHECK",
        "RUNNING",
        "QA_REVIEW",
        "RETRYING",
        "WAITING_OPERATOR",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
    }
    actual_states: set[str] = {state.value for state in TaskState}
    assert actual_states == expected_states


def test_task_state_methods() -> None:
    """Verify TaskState helper methods is_terminal and is_active.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts is_terminal and is_active return correct booleans.
    """
    assert TaskState.COMPLETED.is_terminal() is True
    assert TaskState.FAILED.is_terminal() is True
    assert TaskState.CANCELLED.is_terminal() is True
    assert TaskState.RUNNING.is_terminal() is False

    assert TaskState.RUNNING.is_active() is True
    assert TaskState.PREFLIGHT_CHECK.is_active() is True
    assert TaskState.QA_REVIEW.is_active() is True
    assert TaskState.RETRYING.is_active() is True
    assert TaskState.COMPLETED.is_active() is False


def test_task_node_defaults_and_validation() -> None:
    """Verify TaskNode default state, attempts, and retries.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts correct default values on TaskNode.
    """
    node: TaskNode = TaskNode(
        node_id="node-101",
        workflow_id="wf-999",
        agent_role="neuroimaging_specialist",
        harness_id="agy",
    )
    assert node.state == TaskState.PENDING
    assert node.attempt == 0
    assert node.max_retries == 2
    assert node.envelope is None
    assert node.summary_result is None
    assert node.role == "neuroimaging_specialist"
    assert node.harness == "agy"
    assert node.diagnostic_feedback == []


def test_task_edge_valid() -> None:
    """Verify valid directed TaskEdge between parent and child nodes.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts valid edge creation.
    """
    edge: TaskEdge = TaskEdge(
        workflow_id="wf-1",
        parent_node_id="node-a",
        child_node_id="node-b",
    )
    assert edge.workflow_id == "wf-1"
    assert edge.parent_node_id == "node-a"
    assert edge.child_node_id == "node-b"


def test_task_edge_self_loop_rejection() -> None:
    """Verify that a self-loop edge raises ValidationError.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts validation failure on self loop edge.
    """
    with pytest.raises(ValidationError):
        TaskEdge(
            workflow_id="wf-1",
            parent_node_id="node-a",
            child_node_id="node-a",
        )


def test_neuri_task_envelope_valid() -> None:
    """Verify NeuriTaskEnvelope creation with default budgets and retries.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts task envelope attributes and defaults.
    """
    envelope: NeuriTaskEnvelope = NeuriTaskEnvelope(
        workflow_id="wf-01",
        node_id="node-01",
        agent_role="pipeline_engineer",
        harness_id="codex",
        system_prompt="You are an expert neuroscience pipeline engineer.",
        task_instruction="Write a bash script calling bet on T1w.nii.gz.",
    )
    assert envelope.execution_mode == "headless_json"
    assert envelope.max_tokens_budget == 64000
    assert envelope.max_cost_usd >= 2.00
    assert envelope.attempt_number == 1
    assert envelope.max_retries == 2
    assert envelope.input_artifacts == []
    assert envelope.role == "pipeline_engineer"
    assert envelope.harness == "codex"


def test_neuri_task_envelope_invalid_mode() -> None:
    """Verify that invalid execution mode raises a ValidationError.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts validation error on unsupported execution mode.
    """
    with pytest.raises(ValidationError):
        NeuriTaskEnvelope(
            workflow_id="wf-01",
            node_id="node-01",
            agent_role="coordinator",
            harness_id="agy",
            execution_mode="invalid_streaming_mode",  # type: ignore[arg-type]
            system_prompt="sys",
            task_instruction="inst",
        )


def test_neuri_task_result_success_and_failure() -> None:
    """Verify NeuriTaskResult representing success and failure outcomes.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts task result state representation.
    """
    success_result: NeuriTaskResult = NeuriTaskResult(
        node_id="node-01",
        success=True,
        exit_code=0,
        summary="Brain extraction completed cleanly.",
        artifacts_emitted=[],
        total_tokens=1500,
        cost_usd=0.03,
    )
    assert success_result.success is True
    assert success_result.exit_code == 0
    assert success_result.is_ok() is True
    assert success_result.output_artifacts == []
    assert success_result.tokens_consumed == 1500

    failure_result: NeuriTaskResult = NeuriTaskResult(
        node_id="node-02",
        success=False,
        exit_code=139,
        summary="Segmentation fault during reconstruction.",
        error_message="SIGSEGV in FreeSurfer recon-all",
    )
    assert failure_result.success is False
    assert failure_result.exit_code == 139
    assert failure_result.is_ok() is False


def test_telemetry_event_valid() -> None:
    """Verify TelemetryEvent instantiation with thinking text and token usage.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts telemetry event attributes.
    """
    event: TelemetryEvent = TelemetryEvent(
        event_id="evt-01",
        workflow_id="wf-01",
        node_id="node-01",
        harness_id="agy",
        event_type="thinking_delta",
        thinking_text="Checking affine transform matrix...",
        input_tokens=100,
        output_tokens=25,
        estimated_cost_usd=0.002,
    )
    assert event.event_type == "thinking_delta"
    assert event.thinking_text == "Checking affine transform matrix..."
    assert isinstance(event.timestamp, datetime)


def test_telemetry_event_invalid_type() -> None:
    """Verify that unknown telemetry event_type raises ValidationError.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts validation failure on unknown event type.
    """
    with pytest.raises(ValidationError):
        TelemetryEvent(
            event_id="evt-02",
            workflow_id="wf-01",
            node_id="node-01",
            harness_id="agy",
            event_type="unregistered_telemetry_type",  # type: ignore[arg-type]
        )


def test_niivue_layer_and_scene_spec() -> None:
    """Verify NiiVue layer and scene manifest schema validation.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts NiiVue specification structure.
    """
    layer: NiiVueLayerSpec = NiiVueLayerSpec(
        artifact_uri="cluster:///data/t1.nii.gz",
        colormap="gray",
        opacity=0.8,
    )
    scene: NiiVueSceneSpec = NiiVueSceneSpec(
        scene_id="scene-01",
        title="Structural Overlay",
        volumes=[layer],
        crosshair_mni=(0.0, -20.0, 10.0),
        slice_type="multiplanar",
    )
    assert scene.title == "Structural Overlay"
    assert len(scene.volumes) == 1
    assert scene.crosshair_mni == (0.0, -20.0, 10.0)


def test_niivue_layer_cal_min_max_rejection() -> None:
    """Verify that cal_min > cal_max raises ValidationError in NiiVueLayerSpec.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts calibration range validation error.
    """
    with pytest.raises(ValidationError):
        NiiVueLayerSpec(
            artifact_uri="cluster:///data/t1.nii.gz",
            cal_min=10.0,
            cal_max=5.0,
        )


def test_chat_role_and_turn() -> None:
    """Verify ChatRole enumeration and ChatTurn message representation.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts chat turn model fields and types.
    """
    assert ChatRole.USER.value == "user"
    assert ChatRole.ASSISTANT.value == "assistant"
    assert ChatRole.SYSTEM.value == "system"
    assert ChatRole.OPERATOR.value == "operator"

    turn: ChatTurn = ChatTurn(
        turn_id="turn-1",
        role=ChatRole.USER,
        content="Preprocess sub-01 T1w scan",
    )
    assert turn.role == ChatRole.USER
    assert turn.content == "Preprocess sub-01 T1w scan"


def test_session_event_streaming() -> None:
    """Verify SessionEvent model structure for UI streaming.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts session event serialization and field access.
    """
    event: SessionEvent = SessionEvent(
        event_id="sess-evt-01",
        session_id="session-xyz",
        event_type=SessionEventType.ASSISTANT_CHUNK,
        payload={"chunk": "Preprocessing initiated."},
    )
    assert event.session_id == "session-xyz"
    assert event.event_type == SessionEventType.ASSISTANT_CHUNK
    assert event.payload["chunk"] == "Preprocessing initiated."


def test_task_envelope_and_node_alias_compatibility() -> None:
    """Verify role/harness aliases work interchangeably on Envelope and Node.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts alias acceptance on NeuriTaskEnvelope and TaskNode.
    """
    env: NeuriTaskEnvelope = NeuriTaskEnvelope(
        workflow_id="wf-alias-01",
        node_id="node-alias-01",
        role="neuroimaging_specialist",
        harness="agy",
        system_prompt="sys prompt",
        task_instruction="task instruction",
    )
    assert env.role == "neuroimaging_specialist"
    assert env.agent_role == "neuroimaging_specialist"
    assert env.harness == "agy"
    assert env.harness_id == "agy"

    node: TaskNode = TaskNode(
        node_id="node-alias-01",
        workflow_id="wf-alias-01",
        role="neuroimaging_specialist",
        harness="agy",
    )
    assert node.role == "neuroimaging_specialist"
    assert node.agent_role == "neuroimaging_specialist"
    assert node.harness == "agy"
    assert node.harness_id == "agy"
    return None


def test_task_node_diagnostic_feedback_harmonization() -> None:
    """Verify diagnostic_feedback accepts list, single str, and None.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts normalization of diagnostic feedback across input types.
    """
    node_default: TaskNode = TaskNode(
        node_id="n1", workflow_id="w1", role="role1", harness="agy"
    )
    assert node_default.diagnostic_feedback == []

    node_str: TaskNode = TaskNode(
        node_id="n2",
        workflow_id="w1",
        role="role1",
        harness="agy",
        diagnostic_feedback="Singular matrix: cannot invert affine",
    )
    assert node_str.diagnostic_feedback == [
        "Singular matrix: cannot invert affine"
    ]

    node_list: TaskNode = TaskNode(
        node_id="n3",
        workflow_id="w1",
        role="role1",
        harness="agy",
        diagnostic_feedback=["Error 1", "Error 2"],
    )
    assert node_list.diagnostic_feedback == ["Error 1", "Error 2"]

    node_none: TaskNode = TaskNode(
        node_id="n4",
        workflow_id="w1",
        role="role1",
        harness="agy",
        diagnostic_feedback=None,
    )
    assert node_none.diagnostic_feedback == []
    return None


def test_remote_artifact_posix_path_and_uri_cross_validation() -> None:
    """Verify posix_path must start with '/' and match URI host and path.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts validation of absolute path and URI consistency.
    """
    header: SanitizedNeuroHeader = SanitizedNeuroHeader(
        shape=[256, 256, 176],
        dtype="float32",
    )
    art: RemoteArtifact = RemoteArtifact(
        artifact_id="art-valid",
        uri="host-01:///data/volume.nii.gz",
        host="host-01",
        posix_path="/data/volume.nii.gz",
        modality=ModalityType.T1W,
        sha256_header="a" * 64,
        size_bytes=1024,
        header_summary=header,
    )
    assert art.posix_path.startswith("/")

    with pytest.raises(ValidationError) as exc_rel:
        RemoteArtifact(
            artifact_id="art-rel",
            uri="host-01:///data/volume.nii.gz",
            host="host-01",
            posix_path="data/volume.nii.gz",
            modality=ModalityType.T1W,
            sha256_header="a" * 64,
            size_bytes=1024,
            header_summary=header,
        )
    assert "posix_path must be an absolute path" in str(exc_rel.value)

    with pytest.raises(ValidationError) as exc_mismatch:
        RemoteArtifact(
            artifact_id="art-mismatch",
            uri="host-A:///data/volume.nii.gz",
            host="host-B",
            posix_path="/data/volume.nii.gz",
            modality=ModalityType.T1W,
            sha256_header="a" * 64,
            size_bytes=1024,
            header_summary=header,
        )
    assert "Artifact uri" in str(exc_mismatch.value)
    return None


def test_sanitized_neuro_header_immutability() -> None:
    """Verify SanitizedNeuroHeader is frozen and rejects attribute assignment.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts mutation of any field on SanitizedNeuroHeader is rejected.
    """
    header: SanitizedNeuroHeader = SanitizedNeuroHeader(
        shape=[256, 256, 176],
        dtype="float32",
    )
    with pytest.raises((ValidationError, TypeError)):
        header.phi_sanitized = False  # type: ignore[misc]

    with pytest.raises((ValidationError, TypeError)):
        header.dtype = "int16"  # type: ignore[misc]
    return None

