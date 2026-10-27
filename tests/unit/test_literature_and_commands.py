"""Unit tests for researcher mode, scientific writer, and notebooklm slash commands.

Validates /researcher, /paperback, and /notebooklm routing, 5-pass referee
diagnostic auditing, anti-cliché enforcement, and APA 7th citation formatting.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from neuri.core.blackboard import Blackboard
from neuri.core.config import NeuriConfig, load_config
from neuri.core.orchestrator import DAGOrchestrator
from neuri.core.slash_commands import SlashCommandResult, SlashCommandRouter
from neuri.literature import (
    ApaCitation,
    ApaResolver,
    AuditFinding,
    AuditReport,
    RefereeAuditor,
)


@pytest.fixture
def test_workspace(tmp_path: Path) -> Path:
    """Provide a clean temporary workspace directory.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        Path: Path object
            Temporary workspace directory path.
    """
    ws: Path = tmp_path / "test_workspace"
    ws.mkdir()
    return ws


@pytest.fixture
def test_blackboard(test_workspace: Path) -> Blackboard:
    """Provide an initialized Blackboard instance in test workspace.

    Parameters
    ------------
    test_workspace: Path
        Workspace fixture.

    Returns
    --------
        Blackboard: Blackboard instance
            Initialized SQLite WAL Blackboard object.
    """
    db_file: Path = test_workspace / "state.db"
    bb: Blackboard = Blackboard(db_file)
    return bb


@pytest.fixture
def slash_router(
    test_workspace: Path, test_blackboard: Blackboard
) -> SlashCommandRouter:
    """Provide an initialized SlashCommandRouter.

    Parameters
    ------------
    test_workspace: Path
        Workspace fixture.
    test_blackboard: Blackboard
        Blackboard fixture.

    Returns
    --------
        SlashCommandRouter: SlashCommandRouter instance
            Constructed router instance.
    """
    cfg: NeuriConfig = load_config(test_workspace)
    orch: DAGOrchestrator = DAGOrchestrator(blackboard=test_blackboard)
    router: SlashCommandRouter = SlashCommandRouter(
        workspace_dir=test_workspace,
        config=cfg,
        blackboard=test_blackboard,
        orchestrator=orch,
    )
    return router


def test_researcher_slash_command_help(
    slash_router: SlashCommandRouter,
) -> None:
    """Test /researcher help renders protocol and available commands.

    Parameters
    ------------
    slash_router: SlashCommandRouter
        Active router fixture.

    Returns
    --------
        None: NoneType object
            Asserts markdown output details.
    """
    res: SlashCommandResult = slash_router.execute("/researcher help")
    assert res.success is True
    assert "Autonomous Researcher Mode Protocol" in res.markdown_output
    assert "Step 1: Recall Priors First" in res.markdown_output
    assert "Step 2: Interrogate the Literature" in res.markdown_output
    assert "/researcher priors" in res.markdown_output


def test_researcher_slash_command_priors_and_observe(
    slash_router: SlashCommandRouter,
) -> None:
    """Test /researcher observe and priors commands for memory graph curation.

    Parameters
    ------------
    slash_router: SlashCommandRouter
        Active router fixture.

    Returns
    --------
        None: NoneType object
            Asserts observation recording and retrieval.
    """
    obs_res: SlashCommandResult = slash_router.execute(
        "/researcher observe FreeSurfer CT cortical thickness differs in acute AN"
    )
    assert obs_res.success is True
    assert "Research Observation Recorded" in obs_res.markdown_output

    prior_res: SlashCommandResult = slash_router.execute(
        "/researcher priors FreeSurfer CT"
    )
    assert prior_res.success is True
    assert "Research Priors:" in prior_res.markdown_output


def test_researcher_slash_command_sync(
    slash_router: SlashCommandRouter,
) -> None:
    """Test /researcher sync synchronizes brain vaults and reports metrics.

    Parameters
    ------------
    slash_router: SlashCommandRouter
        Active router fixture.

    Returns
    --------
        None: NoneType object
            Asserts brain synchronization outcome.
    """
    res: SlashCommandResult = slash_router.execute("/researcher sync")
    assert res.success is True
    assert "Research Brain Synchronized" in res.markdown_output


def test_paperback_slash_command_help(
    slash_router: SlashCommandRouter,
) -> None:
    """Test /paperback help displays 4 specialized modes.

    Parameters
    ------------
    slash_router: SlashCommandRouter
        Active router fixture.

    Returns
    --------
        None: NoneType object
            Asserts 4 operational modes described in markdown.
    """
    res: SlashCommandResult = slash_router.execute("/paperback help")
    assert res.success is True
    assert "Scientific Writer & 5-Pass Referee Engine" in res.markdown_output
    assert "Mode 1 (Calibrate):" in res.markdown_output
    assert "Mode 2 (Review):" in res.markdown_output
    assert "Mode 3 (Draft):" in res.markdown_output
    assert "Mode 4 (Cite):" in res.markdown_output


def test_paperback_slash_command_profile_and_exemplars(
    slash_router: SlashCommandRouter,
) -> None:
    """Test /paperback profile and /paperback exemplars diagnostic output.

    Parameters
    ------------
    slash_router: SlashCommandRouter
        Active router fixture.

    Returns
    --------
        None: NoneType object
            Asserts style profile and verbatim exemplars presence.
    """
    prof_res: SlashCommandResult = slash_router.execute("/paperback profile")
    assert prof_res.success is True
    assert "Dr. Daniel Halls" in prof_res.markdown_output

    ex_res: SlashCommandResult = slash_router.execute("/paperback exemplars")
    assert ex_res.success is True
    assert "Halls et al." in ex_res.markdown_output


def test_paperback_slash_command_draft(
    slash_router: SlashCommandRouter,
) -> None:
    """Test /paperback draft generates continuous IMRAD prose without bullet points.

    Parameters
    ------------
    slash_router: SlashCommandRouter
        Active router fixture.

    Returns
    --------
        None: NoneType object
            Asserts two-stage drafting structure.
    """
    res: SlashCommandResult = slash_router.execute(
        "/paperback draft Cortical Gyrification in Anorexia Nervosa"
    )
    assert res.success is True
    assert "Stage 1: Grounded Claim-Citation Skeleton" in res.markdown_output
    assert "Stage 2: Continuous IMRAD Prose" in res.markdown_output
    assert "Cortical differences have been reported" in res.markdown_output


def test_referee_auditor_flags_cliches_and_spellings() -> None:
    """Test RefereeAuditor flags prohibited AI tropes and US spelling slips.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts audit findings and clean corrected prose.
    """
    draft: str = (
        "We delve into the structural MRI data to analyze cortical thickness. "
        "Moreover, the gray matter volume was reduced in the patient cohort. "
        "This pivotal finding underscores the crucial neurobiology."
    )
    auditor: RefereeAuditor = RefereeAuditor()
    report: AuditReport = auditor.review(draft)

    assert len(report.findings) > 0
    issues: list[str] = [f.issue for f in report.findings]
    assert any("delve" in iss for iss in issues)
    assert any("analyze" in iss for iss in issues)
    assert any("gray matter" in iss for iss in issues)

    # Verify British English conversion in corrected prose
    assert "analyse" in report.corrected_text
    assert "grey matter" in report.corrected_text


def test_referee_auditor_flags_impossible_p_values() -> None:
    """Test RefereeAuditor catches mathematically impossible p = 0.000.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts p-value finding flagged in pass 5.
    """
    draft: str = "Group differences were significant (t(48) = 4.12, p = 0.000)."
    auditor: RefereeAuditor = RefereeAuditor()
    report: AuditReport = auditor.review(draft)

    p_findings: list[AuditFinding] = [
        f for f in report.findings if f.pass_number == 5
    ]
    assert len(p_findings) == 1
    assert "p < 0.001" in p_findings[0].suggested_fix


def test_apa_resolver_content_negotiation() -> None:
    """Test ApaResolver resolves DOI to formatted APA 7 string via mock.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts ApaCitation data model structure.
    """
    resolver: ApaResolver = ApaResolver()
    with patch.object(
        resolver,
        "fetch_apa_from_doi",
        return_value="Halls, D. (2022). Title. European Eating Disorders Review.",
    ):
        citation: ApaCitation | None = resolver.resolve("10.1002/erv.2910")
        assert citation is not None
        assert citation.doi == "10.1002/erv.2910"
        assert "European Eating Disorders Review" in citation.apa_string


def test_notebooklm_slash_command_help_and_status(
    slash_router: SlashCommandRouter,
) -> None:
    """Test /notebooklm help and status commands.

    Parameters
    ------------
    slash_router: SlashCommandRouter
        Active router fixture.

    Returns
    --------
        None: NoneType object
            Asserts NotebookLM status reporting.
    """
    help_res: SlashCommandResult = slash_router.execute("/notebooklm help")
    assert help_res.success is True
    assert "Google NotebookLM Integration" in help_res.markdown_output

    status_res: SlashCommandResult = slash_router.execute("/notebooklm status")
    assert status_res.success is True
    assert "NotebookLM CLI Active" in status_res.markdown_output
