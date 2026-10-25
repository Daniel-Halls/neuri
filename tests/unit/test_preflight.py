"""Unit tests for deterministic zero-token PreflightValidator (Task 1.6).

Validates strict PHI sanitization enforcement, coordinate space compatibility,
artifact POSIX path existence, skill catalog registration, and harness binary
checks prior to task dispatch.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from neuri.core.preflight import (
    PreflightCheckResult,
    PreflightValidationError,
    PreflightValidator,
)
from neuri.core.schemas import (
    ModalityType,
    NeuriTaskEnvelope,
    RemoteArtifact,
    SanitizedNeuroHeader,
)


@pytest.fixture
def valid_header() -> SanitizedNeuroHeader:
    """Provide a canonical PHI-sanitized header fixture.

    Parameters
    ------------
    None

    Returns
    --------
        SanitizedNeuroHeader: SanitizedNeuroHeader instance
            Header with phi_sanitized=True.
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
def valid_artifact(
    valid_header: SanitizedNeuroHeader, tmp_path: Path
) -> RemoteArtifact:
    """Provide a valid RemoteArtifact whose posix_path exists on disk.

    Parameters
    ------------
    valid_header: SanitizedNeuroHeader
        Valid header fixture.
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        RemoteArtifact: RemoteArtifact instance
            Valid remote artifact fixture with an existing file.
    """
    sample_file: Path = tmp_path / "sub-01_T1w.nii.gz"
    sample_file.write_bytes(b"dummy-nifti-binary-data")

    artifact: RemoteArtifact = RemoteArtifact(
        artifact_id="art-valid-01",
        uri=f"localhost://{sample_file}",
        host="localhost",
        posix_path=str(sample_file),
        modality=ModalityType.T1W,
        space="MNI152NLin2009cAsym",
        bids_entities={"sub": "01", "datatype": "anat", "suffix": "T1w"},
        sha256_header="b" * 64,
        size_bytes=len(b"dummy-nifti-binary-data"),
        header_summary=valid_header,
        created_at=datetime.now(timezone.utc),
    )
    return artifact


@pytest.fixture
def preflight_envelope(
    valid_artifact: RemoteArtifact,
) -> NeuriTaskEnvelope:
    """Provide a canonical NeuriTaskEnvelope for pre-flight testing.

    Parameters
    ------------
    valid_artifact: RemoteArtifact
        Sample valid artifact fixture.

    Returns
    --------
        NeuriTaskEnvelope: NeuriTaskEnvelope instance
            Canonical task envelope.
    """
    envelope: NeuriTaskEnvelope = NeuriTaskEnvelope(
        workflow_id="wf-preflight-01",
        node_id="node-preflight-01",
        agent_role="neuroimaging_specialist",
        harness_id="agy",
        execution_mode="headless_json",
        system_prompt="Test system prompt",
        task_instruction="Execute brain extraction",
        input_artifacts=[valid_artifact],
        skill_paths=["bids-standard"],
        max_tokens_budget=64000,
        max_cost_usd=2.00,
        attempt_number=1,
        max_retries=2,
    )
    return envelope


# ---------------------------------------------------------------------------
# Test Suite 1: PHI Sanitization Enforcement
# ---------------------------------------------------------------------------


def test_preflight_passes_with_sanitized_phi(
    preflight_envelope: NeuriTaskEnvelope,
) -> None:
    """Test envelope with phi_sanitized=True passes pre-flight validation.

    Parameters
    ------------
    preflight_envelope: NeuriTaskEnvelope
        Valid task envelope fixture.

    Returns
    --------
        None: NoneType object
            Asserts validation passes without errors.
    """
    validator: PreflightValidator = PreflightValidator()
    result: PreflightCheckResult = validator.validate_envelope(
        preflight_envelope
    )
    assert result.passed is True
    assert len(result.errors) == 0


def test_preflight_fails_when_phi_not_sanitized(
    preflight_envelope: NeuriTaskEnvelope,
    tmp_path: Path,
) -> None:
    """Test envelope with phi_sanitized=False is strictly rejected.

    Parameters
    ------------
    preflight_envelope: NeuriTaskEnvelope
        Task envelope fixture.
    tmp_path: Path
        Temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts validation fails and reports PHI error.
    """
    sample_file: Path = tmp_path / "raw.nii.gz"
    sample_file.write_bytes(b"raw-data")

    unsanitized_header: SanitizedNeuroHeader = SanitizedNeuroHeader(
        shape=[256, 256, 176],
        voxel_sizes_mm=[1.0, 1.0, 1.0],
        orientation="RAS",
        dtype="float32",
        phi_sanitized=False,
    )
    unsanitized_art: RemoteArtifact = RemoteArtifact(
        artifact_id="art-unsanitized-01",
        uri=f"localhost://{sample_file}",
        host="localhost",
        posix_path=str(sample_file),
        modality=ModalityType.T1W,
        sha256_header="c" * 64,
        size_bytes=8,
        header_summary=unsanitized_header,
    )
    preflight_envelope.input_artifacts = [unsanitized_art]

    validator: PreflightValidator = PreflightValidator()
    result: PreflightCheckResult = validator.validate_envelope(
        preflight_envelope
    )
    assert result.passed is False
    assert any("phi_sanitized=False" in err for err in result.errors)

    with pytest.raises(PreflightValidationError) as exc_info:
        validator.verify_or_raise(preflight_envelope)
    assert "Pre-flight validation failed" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test Suite 2: Coordinate Space Compatibility
# ---------------------------------------------------------------------------


def test_preflight_space_compatibility_conflicting_standard_spaces(
    preflight_envelope: NeuriTaskEnvelope,
    valid_header: SanitizedNeuroHeader,
    tmp_path: Path,
) -> None:
    """Test mixing conflicting standard spaces (MNI152 and MNI305) produces error.

    Parameters
    ------------
    preflight_envelope: NeuriTaskEnvelope
        Task envelope fixture.
    valid_header: SanitizedNeuroHeader
        Valid header fixture.
    tmp_path: Path
        Temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts conflicting standard spaces produce validation error.
    """
    f1: Path = tmp_path / "f1.nii.gz"
    f2: Path = tmp_path / "f2.nii.gz"
    f1.write_bytes(b"data1")
    f2.write_bytes(b"data2")

    art1: RemoteArtifact = RemoteArtifact(
        artifact_id="art-1",
        uri=f"localhost://{f1}",
        host="localhost",
        posix_path=str(f1),
        modality=ModalityType.T1W,
        space="MNI152NLin2009cAsym",
        sha256_header="d" * 64,
        size_bytes=5,
        header_summary=valid_header,
    )
    art2: RemoteArtifact = RemoteArtifact(
        artifact_id="art-2",
        uri=f"localhost://{f2}",
        host="localhost",
        posix_path=str(f2),
        modality=ModalityType.BOLD,
        space="MNI305",
        sha256_header="e" * 64,
        size_bytes=5,
        header_summary=valid_header,
    )
    preflight_envelope.input_artifacts = [art1, art2]

    validator: PreflightValidator = PreflightValidator()
    result: PreflightCheckResult = validator.validate_envelope(
        preflight_envelope
    )
    assert result.passed is False
    assert any(
        "Multiple conflicting standard spaces" in err for err in result.errors
    )


def test_preflight_space_mix_standard_and_native_produces_warning(
    preflight_envelope: NeuriTaskEnvelope,
    valid_header: SanitizedNeuroHeader,
    tmp_path: Path,
) -> None:
    """Test mixing standard space and native space issues an advisory warning.

    Parameters
    ------------
    preflight_envelope: NeuriTaskEnvelope
        Task envelope fixture.
    valid_header: SanitizedNeuroHeader
        Valid header fixture.
    tmp_path: Path
        Temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts non-blocking warning is emitted.
    """
    f1: Path = tmp_path / "std.nii.gz"
    f2: Path = tmp_path / "nat.nii.gz"
    f1.write_bytes(b"data1")
    f2.write_bytes(b"data2")

    art1: RemoteArtifact = RemoteArtifact(
        artifact_id="art-std",
        uri=f"localhost://{f1}",
        host="localhost",
        posix_path=str(f1),
        modality=ModalityType.T1W,
        space="MNI152NLin2009cAsym",
        sha256_header="f" * 64,
        size_bytes=5,
        header_summary=valid_header,
    )
    art2: RemoteArtifact = RemoteArtifact(
        artifact_id="art-nat",
        uri=f"localhost://{f2}",
        host="localhost",
        posix_path=str(f2),
        modality=ModalityType.T1W,
        space="native",
        sha256_header="0" * 64,
        size_bytes=5,
        header_summary=valid_header,
    )
    preflight_envelope.input_artifacts = [art1, art2]

    validator: PreflightValidator = PreflightValidator()
    result: PreflightCheckResult = validator.validate_envelope(
        preflight_envelope
    )
    assert result.passed is True
    assert any("mix standard space" in warn for warn in result.warnings)


# ---------------------------------------------------------------------------
# Test Suite 3: Localhost POSIX File Existence
# ---------------------------------------------------------------------------


def test_preflight_missing_local_file_fails(
    preflight_envelope: NeuriTaskEnvelope,
    valid_header: SanitizedNeuroHeader,
) -> None:
    """Test missing local artifact posix_path fails pre-flight validation.

    Parameters
    ------------
    preflight_envelope: NeuriTaskEnvelope
        Task envelope fixture.
    valid_header: SanitizedNeuroHeader
        Valid header fixture.

    Returns
    --------
        None: NoneType object
            Asserts non-existent file produces validation error.
    """
    missing_path: str = "/non/existent/neuro/path/sub-99_T1w.nii.gz"
    missing_art: RemoteArtifact = RemoteArtifact(
        artifact_id="art-missing-01",
        uri=f"localhost://{missing_path}",
        host="localhost",
        posix_path=missing_path,
        modality=ModalityType.T1W,
        sha256_header="1" * 64,
        size_bytes=100,
        header_summary=valid_header,
    )
    preflight_envelope.input_artifacts = [missing_art]

    validator: PreflightValidator = PreflightValidator()
    result: PreflightCheckResult = validator.validate_envelope(
        preflight_envelope
    )
    assert result.passed is False
    assert any(
        "Local artifact file not found at POSIX path" in err
        for err in result.errors
    )


# ---------------------------------------------------------------------------
# Test Suite 4: Skill Catalog Validation
# ---------------------------------------------------------------------------


def test_preflight_unregistered_skill_fails(
    preflight_envelope: NeuriTaskEnvelope,
) -> None:
    """Test referencing an unknown/unregistered skill ID produces an error.

    Parameters
    ------------
    preflight_envelope: NeuriTaskEnvelope
        Task envelope fixture.

    Returns
    --------
        None: NoneType object
            Asserts unregistered skill produces validation error.
    """
    preflight_envelope.skill_paths = ["non_existent_magic_skill_99"]
    validator: PreflightValidator = PreflightValidator()
    result: PreflightCheckResult = validator.validate_envelope(
        preflight_envelope
    )
    assert result.passed is False
    assert any(
        "is not registered in the neuroscience skills catalog" in err
        for err in result.errors
    )
