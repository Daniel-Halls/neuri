"""Unit tests for Tier-2 Ecosystem FastMCP servers.

Tests OpenNeuro dataset search and remote staging command generators, Git forge
repository/pipeline queries, Scholar DOI verification and BibTeX registration,
and NeuroResourceRegistry template/atlas databases and BIDS entity validator.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from neuri.core.blackboard import Blackboard
from neuri.mcp_servers.mcp_git_forge import GitForgeMCPServer
from neuri.mcp_servers.mcp_openneuro import OpenNeuroMCPServer
from neuri.mcp_servers.mcp_resources import NeuroResourceRegistry
from neuri.mcp_servers.mcp_scholar import ScholarMCPServer


@pytest.fixture
def scholar_bb(tmp_path: Path) -> Blackboard:
    """Provide temporary Blackboard database for scholar citation tests.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        Blackboard: Blackboard instance
            Blackboard WAL store.
    """
    db_file: Path = tmp_path / "scholar_test.db"
    return Blackboard(db_file)


def test_openneuro_search_and_staging_commands() -> None:
    """Test OpenNeuro search and sparse DataLad/S3 staging command generation.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts search filtering and shell command strings.
    """
    server: OpenNeuroMCPServer = OpenNeuroMCPServer()
    results = server.search_datasets(modality="bold")
    assert len(results) > 0
    assert any(r["dataset_id"] == "ds000228" for r in results)

    # Test DataLad staging command
    datalad_cmd: str = server.build_datalad_staging_command(
        dataset_id="ds000228",
        target_dir="/scratch/bids/ds000228",
        sparse_pattern="sub-01/anat/*",
    )
    assert "datalad install" in datalad_cmd
    assert "datalad get sub-01/anat/*" in datalad_cmd

    # Test S3 staging command
    s3_cmd: str = server.build_s3_staging_command(
        dataset_id="ds000228",
        target_dir="/scratch/bids/ds000228",
        include_pattern="sub-01/*",
    )
    assert "aws s3 sync --no-sign-request" in s3_cmd
    assert "--include \"sub-01/*\"" in s3_cmd


def test_openneuro_jsonrpc_dispatch() -> None:
    """Test OpenNeuro JSON-RPC 2.0 tool invocation.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts JSON-RPC 2.0 response format.
    """
    server: OpenNeuroMCPServer = OpenNeuroMCPServer()
    req = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "get_dataset_metadata",
            "arguments": {"dataset_id": "ds000228"},
        },
        "id": 1,
    }
    resp_str: str = server.handle_jsonrpc(json.dumps(req))
    resp = json.loads(resp_str)
    assert resp["id"] == 1
    assert "result" in resp
    content_text: str = resp["result"]["content"][0]["text"]
    assert "Development of Functional Connectome" in content_text


def test_git_forge_jsonrpc_dispatch() -> None:
    """Test GitForgeMCPServer repository search and issue creation.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts issue creation and workflow run responses.
    """
    server: GitForgeMCPServer = GitForgeMCPServer()

    # Test workflow runs
    runs = server.get_workflow_runs(repo="lab/pipeline")
    assert len(runs) > 0
    assert runs[0]["status"] == "completed"

    # Test JSON-RPC issue creation
    req = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "create_issue",
            "arguments": {
                "repo": "lab/fmri-preproc",
                "title": "Registration divergence in sub-05",
                "body": "QA snapshot shows poor boundary fit.",
                "forge": "github",
            },
        },
        "id": 2,
    }
    resp_str: str = server.handle_jsonrpc(json.dumps(req))
    resp = json.loads(resp_str)
    assert resp["id"] == 2
    assert "result" in resp
    assert "Registration divergence in sub-05" in resp["result"]["content"][0]["text"]


def test_scholar_doi_verification_and_registration(
    scholar_bb: Blackboard, tmp_path: Path
) -> None:
    """Test Scholar DOI verification, BibTeX generation, and Blackboard registration.

    Parameters
    ------------
    scholar_bb: Blackboard
        Blackboard fixture.
    tmp_path: Path
        Pytest temporary directory.

    Returns
    --------
        None: NoneType object
            Asserts DOI verification and ledger storage.
    """
    bib_file: Path = tmp_path / "references.bib"
    scholar: ScholarMCPServer = ScholarMCPServer(
        blackboard=scholar_bb,
        references_bib_path=bib_file,
    )

    # 1. Verify known fMRIPrep DOI
    fmriprep_doi: str = "10.1038/s41592-018-0235-4"
    record = scholar.verify_doi(fmriprep_doi)
    assert record is not None
    assert record["citation_key"] == "esteban2019fmriprep"
    assert "fMRIPrep" in record["title"]

    # 2. Register citation in Blackboard and references.bib
    ok: bool = scholar.register_citation(
        citation_key=record["citation_key"],
        bibtex=record["bibtex"],
        doi=record["doi"],
    )
    assert ok is True

    # Check Blackboard ledger
    stored = scholar_bb.get_citation("esteban2019fmriprep")
    assert stored is not None
    assert stored["verified"] == 1
    assert stored["doi"] == fmriprep_doi

    # Check references.bib written
    assert bib_file.is_file()
    assert "@article{esteban2019fmriprep" in bib_file.read_text()


def test_neuro_resource_registry_and_bids_validation(tmp_path: Path) -> None:
    """Test NeuroResourceRegistry template/atlas catalogs and BIDS filename syntax.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory.

    Returns
    --------
        None: NoneType object
            Asserts standard space catalog and BIDS validation logic.
    """
    db_file: Path = tmp_path / "resources.db"
    registry: NeuroResourceRegistry = NeuroResourceRegistry(db_path=db_file)

    templates = registry.list_templates()
    assert any(t["name"] == "MNI152NLin2009cAsym" for t in templates)

    atlases = registry.list_atlases()
    assert any(a["name"] == "Schaefer2018_400Parcels" for a in atlases)

    containers = registry.list_containers()
    assert any(c["name"] == "fmriprep" for c in containers)

    # Validate valid BIDS filename
    v_ok = registry.validate_bids_entities("sub-01_ses-1_task-rest_bold.nii.gz")
    assert v_ok["is_valid_bids"] is True
    assert v_ok["entities"]["sub"] == "01"
    assert v_ok["entities"]["task"] == "rest"

    # Validate out-of-order BIDS entities (task before sub)
    v_bad = registry.validate_bids_entities("task-rest_sub-01_bold.nii.gz")
    assert v_bad["order_compliant"] is False
