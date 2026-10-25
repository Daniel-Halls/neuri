"""Pytest shared fixtures for Neuri testing suite (M1 and beyond).

Provides temporary workspace directories, mock configurations,
and canonical domain schema objects for unit and integration testing.
"""

from collections.abc import Generator
from datetime import datetime
from pathlib import Path
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
    return SanitizedNeuroHeader(
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
    return RemoteArtifact(
        artifact_id="art-test-001",
        uri="hpc-cluster:///data/bids/sub-01/anat/sub-01_T1w.nii.gz",
        host="hpc-cluster",
        posix_path="/data/bids/sub-01/anat/sub-01_T1w.nii.gz",
        modality=ModalityType.T1W,
        space="MNI152NLin2009cAsym",
        bids_entities={"sub": "01", "datatype": "anat", "suffix": "T1w"},
        sha256_header="abcdef1234567890",
        size_bytes=2097152,
        header_summary=sample_neuro_header,
        created_at=datetime.utcnow(),
    )


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
    return NeuriTaskEnvelope(
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
    return TaskNode(
        node_id="node-test-01",
        workflow_id="wf-test-01",
        agent_role="neuroimaging_specialist",
        harness_id="agy",
        state=TaskState.PENDING,
        attempt=0,
        max_retries=2,
        envelope=sample_task_envelope,
    )


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
    global_dir = tmp_path / ".neuri"
    global_dir.mkdir(parents=True)
    cfg_file = global_dir / "config.toml"
    data: dict[str, Any] = {
        "project": {"default_remote_host": "mock-cluster"},
        "budgets": {"max_node_tokens": 80000, "max_workflow_cost_usd": 15.0},
    }
    with open(cfg_file, "wb") as fh:
        tomli_w.dump(data, fh)
    return cfg_file
