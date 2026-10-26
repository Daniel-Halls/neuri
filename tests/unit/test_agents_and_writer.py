"""Unit tests for role-specialized sub-agents and Scientific Writer.

Tests the 6 specialist agents (pipeline_engineer, neuroimaging_specialist,
electrophys_specialist, compute_operator, critic_qa, scientific_writer),
Critic QA convergence review (R-hat < 1.01, ESS > 400), and the
Anti-Hallucination Citation Gate with COBIDAS Methods drafting.
"""

from pathlib import Path
from typing import Any

import pytest

from neuri.agents.compute_agent import ComputeOperatorAgent
from neuri.agents.critic_qa_agent import CriticQAAgent
from neuri.agents.electrophys_agent import ElectrophysSpecialistAgent
from neuri.agents.neuroimaging_agent import NeuroimagingSpecialistAgent
from neuri.agents.pipeline_agent import PipelineEngineerAgent
from neuri.agents.writer_agent import (
    ScientificWriterAgent,
    UnverifiedCitationError,
)
from neuri.core.blackboard import Blackboard
from neuri.core.schemas import (
    ModalityType,
    NeuriTaskEnvelope,
    RemoteArtifact,
    SanitizedNeuroHeader,
    TaskNode,
    TaskState,
)


@pytest.fixture
def writer_bb(tmp_path: Path) -> Blackboard:
    """Provide a Blackboard instance populated with verified citations and provenance.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        Blackboard: Blackboard instance
            Populated Blackboard store.
    """
    db_file: Path = tmp_path / "writer_test.db"
    bb: Blackboard = Blackboard(db_file)

    # Register verified citations for fMRIPrep and BIDS
    bb.register_citation(
        citation_key="esteban2019fmriprep",
        bibtex=(
            "@article{esteban2019fmriprep,\n"
            "  title={fMRIPrep: a robust preprocessing pipeline},\n"
            "  author={Esteban, Oscar},\n"
            "  journal={Nature Methods},\n"
            "  year={2019}\n"
            "}"
        ),
        title="fMRIPrep",
        authors=["Esteban, Oscar"],
        year=2019,
        verified=True,
    )
    bb.register_citation(
        citation_key="gorgolewski2016bids",
        bibtex=(
            "@article{gorgolewski2016bids,\n"
            "  title={The brain imaging data structure},\n"
            "  author={Gorgolewski, Krzysztof J},\n"
            "  journal={Scientific Data},\n"
            "  year={2016}\n"
            "}"
        ),
        title="BIDS",
        authors=["Gorgolewski, Krzysztof J"],
        year=2016,
        verified=True,
    )
    return bb


def test_specialist_agents_system_prompts_and_envelopes() -> None:
    """Test persona prompts, skill injection, and envelope creation across agents.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts role identification and envelope properties.
    """
    pe: PipelineEngineerAgent = PipelineEngineerAgent()
    assert pe.get_role_name() == "pipeline_engineer"
    assert "bids-standard" in pe.resolve_skill_paths()[0]

    env_pe: NeuriTaskEnvelope = pe.build_envelope(
        workflow_id="wf_01",
        node_id="node_01",
        task_instruction="Audit BIDS hierarchy",
    )
    assert env_pe.agent_role == "pipeline_engineer"
    assert "Pipeline Engineer" in env_pe.system_prompt

    neuro: NeuroimagingSpecialistAgent = NeuroimagingSpecialistAgent()
    assert neuro.get_role_name() == "neuroimaging_specialist"
    assert any("neuroimaging-preproc" in p for p in neuro.resolve_skill_paths())

    ephys: ElectrophysSpecialistAgent = ElectrophysSpecialistAgent()
    assert ephys.get_role_name() == "electrophys_specialist"

    comp: ComputeOperatorAgent = ComputeOperatorAgent()
    assert comp.get_role_name() == "compute_operator"


def test_critic_qa_evaluates_mcmc_convergence() -> None:
    """Test Critic QA approves or rejects based on Gelman-Rubin R-hat and ESS.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts approval for R-hat < 1.01 and rejection for R-hat >= 1.01.
    """
    critic: CriticQAAgent = CriticQAAgent()

    # Converged MCMC run
    ok, msg = critic.evaluate_node_output(
        summary="MCMC sampling completed",
        diagnostics=[],
        artifacts=[],
        r_hat=1.004,
        ess=1200,
    )
    assert ok is True
    assert "QA Approved" in msg

    # Non-converged MCMC run (R-hat >= 1.01)
    fail_rhat, msg_rhat = critic.evaluate_node_output(
        summary="MCMC sampling completed",
        diagnostics=[],
        artifacts=[],
        r_hat=1.035,
        ess=1200,
    )
    assert fail_rhat is False
    assert "R-hat = 1.0350" in msg_rhat

    # Low Effective Sample Size (ESS < 400)
    fail_ess, msg_ess = critic.evaluate_node_output(
        summary="MCMC sampling completed",
        diagnostics=[],
        artifacts=[],
        r_hat=1.002,
        ess=250,
    )
    assert fail_ess is False
    assert "ESS = 250" in msg_ess


def test_anti_hallucination_citation_gate_rejects_hallucinations(
    writer_bb: Blackboard,
) -> None:
    """Test Anti-Hallucination Citation Gate strictly blocks unverified references.

    Parameters
    ------------
    writer_bb: Blackboard
        Blackboard with citations ledger fixture.

    Returns
    --------
        None: NoneType object
            Asserts UnverifiedCitationError is raised on hallucinated keys.
    """
    writer: ScientificWriterAgent = ScientificWriterAgent()

    # Valid text with verified citations
    valid_text: str = (
        "Preprocessing utilized fMRIPrep [@esteban2019fmriprep] on BIDS data "
        "[@gorgolewski2016bids]."
    )
    is_valid, unverified = writer.validate_citations_gate(valid_text, writer_bb)
    assert is_valid is True
    assert len(unverified) == 0

    # Hallucinated citation key
    hallucinated_text: str = (
        "Analysis utilized deep transformer diffusion modeling "
        "[@hallucinated_model_2026; @esteban2019fmriprep]."
    )
    is_val_bad, bad_keys = writer.validate_citations_gate(
        hallucinated_text, writer_bb
    )
    assert is_val_bad is False
    assert "hallucinated_model_2026" in bad_keys


def test_methods_section_drafting_from_provenance(writer_bb: Blackboard) -> None:
    """Test drafting COBIDAS Methods sections in Markdown and LaTeX formats.

    Parameters
    ------------
    writer_bb: Blackboard
        Blackboard fixture.

    Returns
    --------
        None: NoneType object
            Asserts structured Methods text produced.
    """
    wf_id: str = "wf_study_001"
    writer_bb.create_workflow(wf_id, "Multi-subject cortical thickness study")

    # Add completed nodes and artifacts
    node: TaskNode = TaskNode(
        node_id="node_01",
        workflow_id=wf_id,
        agent_role="neuroimaging_specialist",
        harness_id="antigravity",
        state=TaskState.COMPLETED,
        summary_result="Recon-all cortical surface parcellation completed.",
    )
    writer_bb.create_node(node)

    art: RemoteArtifact = RemoteArtifact(
        artifact_id="art_sub01_t1w",
        uri="local:///data/sub-01/anat/sub-01_T1w.nii.gz",
        host="local",
        posix_path="/data/sub-01/anat/sub-01_T1w.nii.gz",
        modality=ModalityType.T1W,
        sha256_header="a" * 64,
        size_bytes=1024,
        created_by_node="node_01",
        header_summary=SanitizedNeuroHeader(
            shape=[256, 256, 176],
            dtype="float32",
            phi_sanitized=True,
        ),
    )
    writer_bb.register_artifact(art, workflow_id=wf_id, node_id="node_01")

    writer: ScientificWriterAgent = ScientificWriterAgent()

    # Draft Markdown
    md_methods: str = writer.draft_methods_section(
        workflow_id=wf_id, blackboard=writer_bb, format_type="markdown"
    )
    assert "## Methods and Materials" in md_methods
    assert "Brain Imaging Data Structure [@gorgolewski2016bids]" in md_methods
    assert "[@esteban2019fmriprep]" in md_methods
    assert "Recon-all cortical surface" in md_methods

    # Draft LaTeX
    latex_methods: str = writer.draft_methods_section(
        workflow_id=wf_id, blackboard=writer_bb, format_type="latex"
    )
    assert "\\section{Methods and Materials}" in latex_methods
    assert "\\cite{gorgolewski2016bids}" in latex_methods
    assert "\\cite{esteban2019fmriprep}" in latex_methods
