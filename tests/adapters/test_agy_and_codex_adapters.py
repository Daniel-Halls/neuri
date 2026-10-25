"""Unit tests for Harness Adapters (Antigravity, Codex, Tier-2, Registry).

Validates command-line generation for headless and interactive modes, argument
flag composition, NDJSON/JSONL stream parsing, adapter discovery, and registry
lookups (Milestone 4).
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import pytest

from neuri.adapters.antigravity import AntigravityAdapter
from neuri.adapters.base import BaseHarnessAdapter, HarnessExecutionError
from neuri.adapters.codex import CodexAdapter
from neuri.adapters.ollama_local import OllamaLocalAdapter
from neuri.adapters.openclaw import OpenClawAdapter
from neuri.adapters.opencode import OpenCodeAdapter
from neuri.adapters.registry import AdapterNotFoundError, AdapterRegistry
from neuri.core.schemas import (
    NeuriTaskEnvelope,
    RemoteArtifact,
    SanitizedNeuroHeader,
    TelemetryEvent,
)
from neuri.core.telemetry import NormalizedStreamResult


@pytest.fixture
def sample_envelope(sample_remote_artifact: RemoteArtifact) -> NeuriTaskEnvelope:
    """Provide a canonical NeuriTaskEnvelope for harness testing.

    Parameters
    ------------
    sample_remote_artifact: RemoteArtifact
        Sample input artifact fixture.

    Returns
    --------
        NeuriTaskEnvelope: NeuriTaskEnvelope instance
            Constructed task envelope.
    """
    envelope: NeuriTaskEnvelope = NeuriTaskEnvelope(
        workflow_id="wf-adapter-01",
        node_id="node-adapter-01",
        agent_role="neuroimaging_specialist",
        harness_id="agy",
        execution_mode="headless_json",
        system_prompt="You are an expert neuroimaging scientist.",
        task_instruction="Perform brain extraction on input T1w volume using BET.",
        input_artifacts=[sample_remote_artifact],
        skill_paths=["skills/bids_io"],
        max_tokens_budget=64000,
        max_cost_usd=2.50,
        attempt_number=1,
        max_retries=2,
    )
    return envelope


# ---------------------------------------------------------------------------
# Test Suite 1: AntigravityAdapter
# ---------------------------------------------------------------------------


def test_antigravity_adapter_properties() -> None:
    """Test AntigravityAdapter reports correct harness ID and executable name.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts harness ID and executable match expected values.
    """
    adapter: AntigravityAdapter = AntigravityAdapter()
    assert adapter.harness_id == "agy"
    assert adapter.executable_name == "agy"


def test_antigravity_adapter_build_headless_command(
    sample_envelope: NeuriTaskEnvelope,
    tmp_path: Path,
) -> None:
    """Test headless command generation includes required agy flags.

    Parameters
    ------------
    sample_envelope: NeuriTaskEnvelope
        Canonical task envelope fixture.
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        None: NoneType object
            Asserts presence of -p, --output-format stream-json, and --mode auto.
    """
    # Create fake skill dir
    skill_dir: Path = tmp_path / "neuro_skill"
    skill_dir.mkdir()
    sample_envelope.skill_paths = [str(skill_dir)]

    adapter: AntigravityAdapter = AntigravityAdapter()
    cmd: list[str] = adapter.build_headless_command(sample_envelope)

    assert cmd[0] == "agy"
    assert "-p" in cmd
    assert "--output-format" in cmd
    fmt_idx: int = cmd.index("--output-format")
    assert cmd[fmt_idx + 1] == "stream-json"
    assert "--mode" in cmd
    mode_idx: int = cmd.index("--mode")
    assert cmd[mode_idx + 1] == "auto"

    assert "--add-dir" in cmd
    dir_idx: int = cmd.index("--add-dir")
    assert cmd[dir_idx + 1] == str(skill_dir)

    prompt_idx: int = cmd.index("-p") + 1
    prompt_str: str = cmd[prompt_idx]
    assert "System: You are an expert neuroimaging scientist." in prompt_str
    assert "Perform brain extraction on input T1w volume" in prompt_str
    assert "art-test-001" in prompt_str


def test_antigravity_adapter_diagnostic_feedback_in_prompt(
    sample_envelope: NeuriTaskEnvelope,
) -> None:
    """Test diagnostic feedback from previous failure is appended to prompt.

    Parameters
    ------------
    sample_envelope: NeuriTaskEnvelope
        Canonical task envelope fixture.

    Returns
    --------
        None: NoneType object
            Asserts feedback text appears in generated prompt.
    """
    sample_envelope.diagnostic_feedback = (
        "Previous attempt failed with BET fractional intensity error"
    )
    adapter: AntigravityAdapter = AntigravityAdapter()
    cmd: list[str] = adapter.build_headless_command(sample_envelope)

    prompt_str: str = cmd[cmd.index("-p") + 1]
    assert "Previous Attempt Feedback: Previous attempt failed" in prompt_str


def test_antigravity_adapter_build_interactive_command(
    sample_envelope: NeuriTaskEnvelope,
) -> None:
    """Test interactive command uses -i flag for terminal escalation.

    Parameters
    ------------
    sample_envelope: NeuriTaskEnvelope
        Canonical task envelope fixture.

    Returns
    --------
        None: NoneType object
            Asserts -i flag and instruction are in command arguments.
    """
    adapter: AntigravityAdapter = AntigravityAdapter()
    cmd: list[str] = adapter.build_interactive_command(sample_envelope)
    assert cmd[0] == "agy"
    assert "-i" in cmd
    assert sample_envelope.task_instruction in cmd


def test_antigravity_adapter_parse_stream_line() -> None:
    """Test stream line parsing extracts typed TelemetryEvents.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts normalizer extracts token usage and visible content.
    """
    adapter: AntigravityAdapter = AntigravityAdapter()
    raw_json: str = json.dumps(
        {
            "event": "chunk",
            "content": "Step 1 <thinking>analyzing</thinking> Complete",
        }
    )
    res: NormalizedStreamResult = adapter.parse_stream_line(raw_json)
    assert res.content_delta == "Step 1  Complete"
    assert len(res.events) == 1
    assert res.events[0].event_type == "thinking_delta"
    assert res.events[0].thinking_text == "analyzing"


# ---------------------------------------------------------------------------
# Test Suite 2: CodexAdapter
# ---------------------------------------------------------------------------


def test_codex_adapter_properties() -> None:
    """Test CodexAdapter reports correct harness ID and executable name.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts harness ID is 'codex' and executable is 'codex'.
    """
    adapter: CodexAdapter = CodexAdapter()
    assert adapter.harness_id == "codex"
    assert adapter.executable_name == "codex"


def test_codex_adapter_build_headless_command(
    sample_envelope: NeuriTaskEnvelope,
) -> None:
    """Test headless command generation includes 'exec' and '--json'.

    Parameters
    ------------
    sample_envelope: NeuriTaskEnvelope
        Canonical task envelope fixture.

    Returns
    --------
        None: NoneType object
            Asserts presence of exec and --json in arguments list.
    """
    adapter: CodexAdapter = CodexAdapter()
    cmd: list[str] = adapter.build_headless_command(sample_envelope)
    assert cmd[0] == "codex"
    assert cmd[1] == "exec"
    assert cmd[2] == "--json"
    assert "Perform brain extraction on input T1w volume" in cmd[3]


def test_codex_adapter_build_interactive_command(
    sample_envelope: NeuriTaskEnvelope,
) -> None:
    """Test interactive command for codex passes instruction prompt directly.

    Parameters
    ------------
    sample_envelope: NeuriTaskEnvelope
        Canonical task envelope fixture.

    Returns
    --------
        None: NoneType object
            Asserts executable and instruction are passed.
    """
    adapter: CodexAdapter = CodexAdapter()
    cmd: list[str] = adapter.build_interactive_command(sample_envelope)
    assert cmd[0] == "codex"
    assert cmd[1] == sample_envelope.task_instruction


# ---------------------------------------------------------------------------
# Test Suite 3: Tier-2 Adapters (OpenCode, OpenClaw, Ollama)
# ---------------------------------------------------------------------------


def test_opencode_adapter_command(
    sample_envelope: NeuriTaskEnvelope,
) -> None:
    """Test OpenCodeAdapter builds headless command with run --json.

    Parameters
    ------------
    sample_envelope: NeuriTaskEnvelope
        Canonical task envelope fixture.

    Returns
    --------
        None: NoneType object
            Asserts opencode run --json arguments.
    """
    adapter: OpenCodeAdapter = OpenCodeAdapter()
    assert adapter.harness_id == "opencode"
    cmd: list[str] = adapter.build_headless_command(sample_envelope)
    assert cmd[:3] == ["opencode", "run", "--json"]


def test_openclaw_adapter_command(
    sample_envelope: NeuriTaskEnvelope,
) -> None:
    """Test OpenClawAdapter builds headless command with --headless --stream-json.

    Parameters
    ------------
    sample_envelope: NeuriTaskEnvelope
        Canonical task envelope fixture.

    Returns
    --------
        None: NoneType object
            Asserts openclaw headless streaming flags.
    """
    adapter: OpenClawAdapter = OpenClawAdapter()
    assert adapter.harness_id == "openclaw"
    cmd: list[str] = adapter.build_headless_command(sample_envelope)
    assert cmd[0] == "openclaw"
    assert "--headless" in cmd
    assert "--stream-json" in cmd


def test_ollama_adapter_command(
    sample_envelope: NeuriTaskEnvelope,
) -> None:
    """Test OllamaLocalAdapter builds run command with target model.

    Parameters
    ------------
    sample_envelope: NeuriTaskEnvelope
        Canonical task envelope fixture.

    Returns
    --------
        None: NoneType object
            Asserts ollama run <model> arguments.
    """
    adapter: OllamaLocalAdapter = OllamaLocalAdapter(default_model="llama3.1")
    assert adapter.harness_id == "ollama_local"
    cmd: list[str] = adapter.build_headless_command(sample_envelope)
    assert cmd[:3] == ["ollama", "run", "llama3.1"]


# ---------------------------------------------------------------------------
# Test Suite 4: AdapterRegistry
# ---------------------------------------------------------------------------


def test_adapter_registry_resolves_standard_harnesses() -> None:
    """Test AdapterRegistry successfully retrieves all standard harness drivers.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts agy, codex, opencode, openclaw, and ollama resolution.
    """
    registry: AdapterRegistry = AdapterRegistry()
    assert isinstance(registry.get_adapter("agy"), AntigravityAdapter)
    assert isinstance(registry.get_adapter("antigravity"), AntigravityAdapter)
    assert isinstance(registry.get_adapter("codex"), CodexAdapter)
    assert isinstance(registry.get_adapter("opencode"), OpenCodeAdapter)
    assert isinstance(registry.get_adapter("openclaw"), OpenClawAdapter)
    assert isinstance(registry.get_adapter("ollama"), OllamaLocalAdapter)
    assert isinstance(registry.get_adapter("ollama_local"), OllamaLocalAdapter)


def test_adapter_registry_raises_on_unknown_harness() -> None:
    """Test AdapterRegistry raises AdapterNotFoundError for unregistered IDs.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts AdapterNotFoundError is raised with descriptive message.
    """
    registry: AdapterRegistry = AdapterRegistry()
    with pytest.raises(AdapterNotFoundError) as exc_info:
        registry.get_adapter("unknown_robot_harness")

    err: AdapterNotFoundError = exc_info.value
    assert err.harness_id == "unknown_robot_harness"
    assert "No harness adapter registered" in str(err)


def test_adapter_registry_custom_registration() -> None:
    """Test registering a custom adapter instance overrides or adds to registry.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts custom adapter registration is accessible.
    """
    registry: AdapterRegistry = AdapterRegistry()
    custom: OllamaLocalAdapter = OllamaLocalAdapter(default_model="mistral")
    registry.register_adapter("custom-mistral", custom)
    retrieved: BaseHarnessAdapter = registry.get_adapter("custom-mistral")
    assert retrieved is custom


def test_adapter_registry_list_all() -> None:
    """Test list_all returns full set of registered identifiers.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts all default harness keys appear in list.
    """
    registry: AdapterRegistry = AdapterRegistry()
    all_keys: list[str] = registry.list_all()
    assert "agy" in all_keys
    assert "codex" in all_keys
    assert "ollama" in all_keys
    assert "openclaw" in all_keys
    assert "opencode" in all_keys
