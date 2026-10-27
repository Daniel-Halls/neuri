"""Unit tests for Neuri dynamic rule loading and agent prompt composition.

Verifies that default rule directories are empty, rules are loaded dynamically
when rule files are present, and agent task envelopes contain no hardcoded rules.
"""

from pathlib import Path

import pytest

from neuri.agents.pipeline_agent import PipelineEngineerAgent
from neuri.core.blackboard import Blackboard
from neuri.core.config import ConfigManager
from neuri.core.orchestrator import DAGOrchestrator
from neuri.core.paths import PathResolver
from neuri.core.rules import RuleLoader
from neuri.core.schemas import NeuriTaskEnvelope, TaskNode, TaskState


def test_default_rules_directory_exists() -> None:
    """Test that the default root rules directory exists.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts directory exists and is a valid directory.
    """
    rules_dir: Path = PathResolver.get_default_rules_dir()
    assert rules_dir.is_dir()


def test_rule_loader_returns_empty_when_no_rules_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test RuleLoader returns an empty string when rule directories are empty.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.
    monkeypatch: pytest.MonkeyPatch
        Pytest monkeypatch fixture.

    Returns
    --------
        None: NoneType object
            Asserts empty string return for both general and role rules.
    """
    empty_rules: Path = tmp_path / "empty_rules"
    empty_rules.mkdir()
    monkeypatch.setattr(
        PathResolver,
        "resolve_rules_dirs",
        lambda workspace_dir=None: [empty_rules],
    )
    loader: RuleLoader = RuleLoader()
    general_rules: str = loader.load_rules()
    role_rules: str = loader.load_rules(role="pipeline_engineer")
    assert general_rules == ""
    assert role_rules == ""


def test_rule_loader_loads_general_and_role_rules(tmp_path: Path) -> None:
    """Test RuleLoader loads markdown files from an active rules directory.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts general and role-specific rules are loaded correctly.
    """
    rules_dir: Path = tmp_path / "rules"
    rules_dir.mkdir()

    general_file: Path = rules_dir / "general.md"
    general_file.write_text(
        "# General Guidelines\nAlways write clean code.",
        encoding="utf-8",
    )

    role_file: Path = rules_dir / "pipeline_engineer.md"
    role_file.write_text(
        "# Pipeline Rules\nValidate directory paths before execution.",
        encoding="utf-8",
    )

    loader: RuleLoader = RuleLoader(rules_dir=rules_dir)
    loaded_role_rules: str = loader.load_rules(role="pipeline_engineer")
    assert "Always write clean code." in loaded_role_rules
    assert "Validate directory paths before execution." in loaded_role_rules

    loaded_other_rules: str = loader.load_rules(role="critic_qa")
    assert "Always write clean code." in loaded_other_rules
    assert "Validate directory paths" not in loaded_other_rules


def test_specialist_agent_envelope_has_no_hardcoded_rules() -> None:
    """Test that agent task envelope contains persona without hardcoded rules.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts system prompt contains role identity and no rules block.
    """
    agent: PipelineEngineerAgent = PipelineEngineerAgent()
    envelope: NeuriTaskEnvelope = agent.build_envelope(
        workflow_id="wf_rule_test",
        node_id="node_rule_test",
        task_instruction="Process data",
    )
    assert "Pipeline Engineer" in envelope.system_prompt
    assert "Operational Rules:" not in envelope.system_prompt
    assert "1. Validating and enforcing BIDS" not in envelope.system_prompt


def test_rule_loader_loads_master_prompt(tmp_path: Path) -> None:
    """Test loading master grounding prompt from .neuri/master_prompt.md.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts master prompt content is returned and injected.
    """
    ws_dot: Path = tmp_path / ".neuri"
    ws_dot.mkdir(parents=True)
    master_file: Path = ws_dot / "master_prompt.md"
    master_file.write_text(
        "You are Neuri, an autonomous scientific neuroscience assistant.",
        encoding="utf-8",
    )

    loaded: str = RuleLoader.load_master_prompt(workspace_dir=tmp_path)
    assert "autonomous scientific neuroscience assistant" in loaded


def test_agent_envelope_dynamically_injects_rules(tmp_path: Path) -> None:
    """Test agent envelope injects rules when a workspace rule file is present.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts rule content is included in envelope system prompt.
    """
    ws_rules: Path = tmp_path / ".neuri" / "rules"
    ws_rules.mkdir(parents=True)
    rule_doc: Path = ws_rules / "custom_rule.md"
    rule_doc.write_text("Rule 42: Always use UTC.", encoding="utf-8")

    loader: RuleLoader = RuleLoader(workspace_dir=tmp_path)
    rules_str: str = loader.load_rules()
    assert "Rule 42: Always use UTC." in rules_str


def test_init_project_workspace_scaffolds_empty_rules_dir(
    tmp_path: Path,
) -> None:
    """Test init_project_workspace scaffolds an empty .neuri/rules directory.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts .neuri/rules exists and is an empty directory.
    """
    manager: ConfigManager = ConfigManager(project_root=tmp_path)
    result = manager.init_project_workspace()
    assert "rules_dir" in result
    rules_dir: Path = result["rules_dir"]
    assert rules_dir.is_dir()
    assert len(list(rules_dir.iterdir())) == 0


def test_orchestrator_unmatched_prompt_does_not_force_bids_standard(
    tmp_path: Path,
) -> None:
    """Test orchestrator plans general task without forced neuro skills.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts planned task has no skill_paths and coordinator role.
    """
    bb: Blackboard = Blackboard(tmp_path / "test_rules_state.db")
    orch: DAGOrchestrator = DAGOrchestrator(blackboard=bb)
    wf_id: str = orch.plan_workflow_from_prompt("What is 2 + 2?")
    ready: list[TaskNode] = bb.get_ready_nodes(wf_id)
    assert len(ready) == 1
    node: TaskNode = ready[0]
    assert node.agent_role == "coordinator"
    assert node.envelope.skill_paths == []
    assert node.envelope.task_instruction == "What is 2 + 2?"
