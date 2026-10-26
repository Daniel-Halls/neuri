"""Pytest shared fixtures for Neuri testing suite (M1 and beyond).

Provides temporary workspace directories, mock configurations,
and canonical domain schema objects for unit and integration testing.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import struct
from typing import Any

import pytest
import tomli_w

from neuri.core.config import (
    BudgetConfig,
    HarnessRoutingConfig,
    NeuriConfig,
    WorkspaceConfig,
)
from neuri.core.schemas import (
    ModalityType,
    NeuriTaskEnvelope,
    RemoteArtifact,
    SanitizedNeuroHeader,
    TaskNode,
    TaskState,
)


@pytest.fixture
def sample_neuro_header() -> SanitizedNeuroHeader:
    """Provide a canonical SanitizedNeuroHeader fixture for testing.

    Parameters
    ------------
    None

    Returns
    --------
        SanitizedNeuroHeader: SanitizedNeuroHeader object
            Canonical structural neuroimaging metadata header.
    """
    header: SanitizedNeuroHeader = SanitizedNeuroHeader(
        shape=[256, 256, 176],
        voxel_sizes_mm=[1.0, 1.0, 1.0],
        orientation="RAS",
        tr_seconds=2.0,
        sampling_freq_hz=None,
        channel_count=None,
        dtype="float32",
        nan_count=0,
        inf_count=0,
        value_range=(0.0, 1000.0),
        phi_sanitized=True,
    )
    return header


@pytest.fixture
def sample_remote_artifact(
    sample_neuro_header: SanitizedNeuroHeader,
) -> RemoteArtifact:
    """Provide a canonical RemoteArtifact fixture referencing a NIfTI volume.

    Parameters
    ------------
    sample_neuro_header: SanitizedNeuroHeader
        Sanitized metadata fixture.

    Returns
    --------
        RemoteArtifact: RemoteArtifact object
            Canonical remote artifact pointing to a T1w volume.
    """
    artifact: RemoteArtifact = RemoteArtifact(
        artifact_id="art-test-001",
        uri="hpc-cluster:///data/bids/sub-01/anat/sub-01_T1w.nii.gz",
        host="hpc-cluster",
        posix_path="/data/bids/sub-01/anat/sub-01_T1w.nii.gz",
        modality=ModalityType.T1W,
        space="MNI152NLin2009cAsym",
        bids_entities={"sub": "01", "datatype": "anat", "suffix": "T1w"},
        sha256_header="abcdef1234567890" * 4,
        size_bytes=2097152,
        header_summary=sample_neuro_header,
        created_at=datetime.now(timezone.utc),
    )
    return artifact


@pytest.fixture
def sample_task_envelope(
    sample_remote_artifact: RemoteArtifact,
) -> NeuriTaskEnvelope:
    """Provide a canonical NeuriTaskEnvelope fixture.

    Parameters
    ------------
    sample_remote_artifact: RemoteArtifact
        Sample input artifact fixture.

    Returns
    --------
        NeuriTaskEnvelope: NeuriTaskEnvelope object
            Canonical task envelope ready for harness dispatch.
    """
    envelope: NeuriTaskEnvelope = NeuriTaskEnvelope(
        workflow_id="wf-test-01",
        node_id="node-test-01",
        agent_role="neuroimaging_specialist",
        harness_id="agy",
        execution_mode="headless_json",
        system_prompt="You are a neuroimaging specialist.",
        task_instruction="Perform brain extraction using BET.",
        input_artifacts=[sample_remote_artifact],
        max_tokens_budget=64000,
        max_cost_usd=2.00,
        attempt_number=1,
        max_retries=2,
    )
    return envelope


@pytest.fixture
def sample_task_node(
    sample_task_envelope: NeuriTaskEnvelope,
) -> TaskNode:
    """Provide a canonical TaskNode fixture.

    Parameters
    ------------
    sample_task_envelope: NeuriTaskEnvelope
        Sample task envelope fixture.

    Returns
    --------
        TaskNode: TaskNode object
            Canonical task node in PENDING state.
    """
    node: TaskNode = TaskNode(
        node_id="node-test-01",
        workflow_id="wf-test-01",
        agent_role="neuroimaging_specialist",
        harness_id="agy",
        state=TaskState.PENDING,
        attempt=0,
        max_retries=2,
        envelope=sample_task_envelope,
    )
    return node


@pytest.fixture
def mock_global_config_path(tmp_path: Path) -> Path:
    """Provide a temporary global config.toml path with custom budgets.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        Path: Path object
            Path to written global config file.
    """
    global_dir: Path = tmp_path / ".neuri"
    global_dir.mkdir(parents=True)
    cfg_file: Path = global_dir / "config.toml"
    data: dict[str, Any] = {
        "project": {"default_remote_host": "mock-cluster"},
        "budgets": {"max_node_tokens": 80000, "max_workflow_cost_usd": 15.0},
    }
    with open(cfg_file, "wb") as fh:
        tomli_w.dump(data, fh)
    return cfg_file


def build_synthetic_nifti_bytes(
    orientation: str = "RAS",
    descrip_phi: bytes = b"Patient: John Doe DOB 1980-01-01",
) -> bytes:
    """Build a valid 352-byte binary NIfTI-1 header + 64-voxel payload.

    Parameters
    ------------
    orientation: str
        Target orientation ('RAS' or 'LPS'). Defaults to 'RAS'.
    descrip_phi: bytes
        Injected PHI string in descrip field (bytes 148..228).

    Returns
    --------
        bytes: bytes object
            Raw NIfTI-1 file bytes (<1 KB).
    """
    hdr: bytearray = bytearray(352)
    struct.pack_into("<i", hdr, 0, 348)
    hdr[14:32] = b"DB_SECRET_PATIENT\x00"
    dims: tuple[int, ...] = (4, 4, 4, 4, 2, 1, 1, 1)
    struct.pack_into("<8h", hdr, 40, *dims)
    struct.pack_into("<h", hdr, 70, 16)
    struct.pack_into("<h", hdr, 72, 32)
    pixdims: tuple[float, ...] = (1.0, 2.0, 2.0, 2.0, 1.5, 0.0, 0.0, 0.0)
    struct.pack_into("<8f", hdr, 76, *pixdims)
    struct.pack_into("<f", hdr, 108, 352.0)
    hdr[148 : 148 + min(80, len(descrip_phi))] = descrip_phi[:80]
    hdr[228:252] = b"AUX_PHI_RECORD_99\x00\x00\x00\x00\x00\x00\x00"
    struct.pack_into("<h", hdr, 252, 1)
    struct.pack_into("<h", hdr, 254, 1)
    sign: float = -2.0 if orientation == "LPS" else 2.0
    struct.pack_into("<4f", hdr, 280, sign, 0.0, 0.0, 0.0)
    struct.pack_into("<4f", hdr, 296, 0.0, sign, 0.0, 0.0)
    struct.pack_into("<4f", hdr, 312, 0.0, 0.0, 2.0, 0.0)
    hdr[344:348] = b"n+1\x00"
    payload: bytes = struct.pack("<128f", *[float(i) for i in range(128)])
    return bytes(hdr) + payload


@pytest.fixture
def synthetic_nifti_ras_path(tmp_path: Path) -> Path:
    """Create a synthetic RAS+ NIfTI-1 file containing PHI in header fields.

    Parameters
    ------------
    tmp_path: Path
        Temporary directory fixture.

    Returns
    --------
        Path: Path object
            Path to synthetic RAS+ NIfTI-1 file.
    """
    nii_path: Path = tmp_path / "sub-01_ses-01_task-rest_bold.nii"
    nii_path.write_bytes(build_synthetic_nifti_bytes(orientation="RAS"))
    return nii_path


@pytest.fixture
def synthetic_nifti_lps_path(tmp_path: Path) -> Path:
    """Create a synthetic LPS+ NIfTI-1 file containing PHI in header fields.

    Parameters
    ------------
    tmp_path: Path
        Temporary directory fixture.

    Returns
    --------
        Path: Path object
            Path to synthetic LPS+ NIfTI-1 file.
    """
    nii_path: Path = tmp_path / "sub-01_T1w.nii"
    nii_path.write_bytes(build_synthetic_nifti_bytes(orientation="LPS"))
    return nii_path


@pytest.fixture
def synthetic_bids_dir(tmp_path: Path) -> Path:
    """Create a miniature valid BIDS dataset directory tree (<100 KB).

    Parameters
    ------------
    tmp_path: Path
        Temporary directory fixture.

    Returns
    --------
        Path: Path object
            Root path of synthetic BIDS dataset.
    """
    bids_root: Path = tmp_path / "bids_dataset"
    anat_dir: Path = bids_root / "sub-01" / "anat"
    func_dir: Path = bids_root / "sub-01" / "func"
    anat_dir.mkdir(parents=True)
    func_dir.mkdir(parents=True)

    desc: dict[str, Any] = {
        "Name": "Synthetic Neuri Test Dataset",
        "BIDSVersion": "1.9.0",
        "DatasetType": "raw",
    }
    (bids_root / "dataset_description.json").write_text(
        json.dumps(desc, indent=2), encoding="utf-8"
    )
    (anat_dir / "sub-01_T1w.nii").write_bytes(
        build_synthetic_nifti_bytes(orientation="RAS")
    )
    (func_dir / "sub-01_task-rest_bold.nii").write_bytes(
        build_synthetic_nifti_bytes(orientation="RAS")
    )
    return bids_root

