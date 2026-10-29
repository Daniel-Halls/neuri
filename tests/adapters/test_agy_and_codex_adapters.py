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
            Asserts presence of -p and --output-format stream-json.
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
    """Test OpenClawAdapter builds headless command with agent --local --json.

    Parameters
    ------------
    sample_envelope: NeuriTaskEnvelope
        Canonical task envelope fixture.

    Returns
    --------
        None: NoneType object
            Asserts openclaw headless agent flags.
    """
    adapter: OpenClawAdapter = OpenClawAdapter()
    assert adapter.harness_id == "openclaw"
    cmd: list[str] = adapter.build_headless_command(sample_envelope)
    assert cmd[0] == "openclaw"
    assert "agent" in cmd
    assert "--local" in cmd
    assert "--json" in cmd
    assert "--message" in cmd


def test_ollama_adapter_command(
    sample_envelope: NeuriTaskEnvelope,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test OllamaLocalAdapter dynamically queries available models for run.

    Parameters
    ------------
    sample_envelope: NeuriTaskEnvelope
        Canonical task envelope fixture.
    monkeypatch: pytest.MonkeyPatch
        Pytest monkeypatch fixture.

    Returns
    --------
        None: NoneType object
            Asserts ollama run uses dynamically discovered model.
    """
    adapter: OllamaLocalAdapter = OllamaLocalAdapter()
    monkeypatch.setattr(
        adapter,
        "list_available_models",
        lambda: ["discovered-local-model:1b"],
    )
    assert adapter.harness_id == "ollama"
    cmd: list[str] = adapter.build_headless_command(sample_envelope)
    assert cmd[:3] == ["ollama", "run", "discovered-local-model:1b"]
    assert "Perform brain extraction on input T1w volume" in cmd[3]


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
    custom: OllamaLocalAdapter = OllamaLocalAdapter()
    registry.register_adapter("custom-local", custom)
    retrieved: BaseHarnessAdapter = registry.get_adapter("custom-local")
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


def test_agy_stream_json_step_update_and_result_parsing() -> None:
    """Test parsing real agy stream-json NDJSON lines into clean chat text.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts TelemetryTap accumulates text_delta and usage from agy.
    """
    from neuri.core.telemetry import TelemetryTap

    tap: TelemetryTap = TelemetryTap(
        workflow_id="wf-agy-real",
        node_id="node-agy-real",
        harness_id="agy",
    )
    lines: list[str] = [
        json.dumps({"event": "init", "conversation_id": "conv-123"}),
        json.dumps(
            {
                "event": "step_update",
                "step_update": {
                    "step_index": 1,
                    "state": "ACTIVE",
                    "step_type": "agent_response",
                    "text_delta": "Hello from ",
                },
            }
        ),
        json.dumps(
            {
                "event": "step_update",
                "step_update": {
                    "step_index": 1,
                    "state": "DONE",
                    "step_type": "agent_response",
                    "text_delta": "Neuri!",
                    "usage": {
                        "input_tokens": 100,
                        "output_tokens": 10,
                        "thinking_tokens": 0,
                        "cache_read_tokens": 0,
                    },
                },
            }
        ),
        json.dumps(
            {
                "event": "result",
                "result": {
                    "status": "SUCCESS",
                    "response": "Hello from Neuri!\n",
                    "usage": {
                        "input_tokens": 100,
                        "output_tokens": 10,
                        "thinking_tokens": 0,
                        "cache_read_tokens": 0,
                    },
                },
            }
        ),
    ]
    for line in lines:
        tap.process_chunk(line + "\n")

    assert tap.get_clean_text() == "Hello from Neuri!"
    assert tap.get_total_tokens() == 110


@pytest.mark.asyncio
async def test_base_harness_adapter_streams_content_and_stderr() -> None:
    """Test BaseHarnessAdapter streams content_delta and stderr raw_stream.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts on_event receives content deltas and stderr text.
    """
    from unittest.mock import AsyncMock, MagicMock
    from neuri.adapters.antigravity import AntigravityAdapter
    from neuri.core.telemetry import TelemetryTap

    adapter: AntigravityAdapter = AntigravityAdapter()
    tap: TelemetryTap = TelemetryTap(
        workflow_id="wf-test-stream",
        node_id="node-test-stream",
        harness_id="agy",
    )

    emitted: list[TelemetryEvent] = []

    # 1. Test stdout streaming
    mock_process: MagicMock = MagicMock()
    mock_process.stdout = AsyncMock()
    mock_process.stdout.readline.side_effect = [
        json.dumps(
            {
                "event": "chunk",
                "content": "<thinking>reasoning</thinking>Hello world!",
            }
        ).encode("utf-8")
        + b"\n",
        b"",
    ]

    accumulated: list[str] = []
    await adapter._stream_stdout(
        process=mock_process,
        tap=tap,
        accumulated_output=accumulated,
        on_event=lambda ev: emitted.append(ev),
    )

    assert len(accumulated) == 1
    # Expect thinking_delta and content_delta
    event_types: list[str] = [e.event_type for e in emitted]
    assert "thinking_delta" in event_types
    assert "content_delta" in event_types

    content_events: list[TelemetryEvent] = [
        e for e in emitted if e.event_type == "content_delta"
    ]
    assert len(content_events) == 1
    assert content_events[0].content_text == "Hello world!"

    # 2. Test stderr streaming
    mock_process.stderr = AsyncMock()
    mock_process.stderr.readline.side_effect = [
        b"[WARN] GPU memory running low\n",
        b"",
    ]
    stderr_lines: list[str] = []
    await adapter._stream_stderr(
        process=mock_process,
        stderr_lines=stderr_lines,
        on_event=lambda ev: emitted.append(ev),
        workflow_id="wf-test-stream",
        node_id="node-test-stream",
    )

    assert len(stderr_lines) == 1
    stderr_events: list[TelemetryEvent] = [
        e for e in emitted if e.event_type == "raw_stream"
    ]
    assert len(stderr_events) == 1
    assert "[WARN] GPU memory running low" in str(stderr_events[0].raw_text)


def test_adapters_include_custom_model_flag(
    sample_envelope: NeuriTaskEnvelope,
) -> None:
    """Test all harness adapters incorporate envelope.model when specified.

    Parameters
    ------------
    sample_envelope: NeuriTaskEnvelope
        Canonical task envelope fixture.

    Returns
    --------
        None: NoneType object
            Asserts presence of model arguments across all adapters.
    """
    sample_envelope.model = "agy-discovered-model-alpha"
    agy: AntigravityAdapter = AntigravityAdapter()
    agy_cmd: list[str] = agy.build_headless_command(sample_envelope)
    assert "--model" in agy_cmd
    assert agy_cmd[agy_cmd.index("--model") + 1] == "agy-discovered-model-alpha"

    sample_envelope.model = "codex-discovered-model-beta"
    codex: CodexAdapter = CodexAdapter()
    codex_cmd: list[str] = codex.build_headless_command(sample_envelope)
    assert "--model" in codex_cmd
    assert (
        codex_cmd[codex_cmd.index("--model") + 1]
        == "codex-discovered-model-beta"
    )

    sample_envelope.model = "ollama-discovered-model:tag"
    ollama: OllamaLocalAdapter = OllamaLocalAdapter()
    ollama_cmd: list[str] = ollama.build_headless_command(sample_envelope)
    assert "ollama-discovered-model:tag" in ollama_cmd

    sample_envelope.model = "opencode-discovered-model"
    opencode: OpenCodeAdapter = OpenCodeAdapter()
    opencode_cmd: list[str] = opencode.build_headless_command(sample_envelope)
    assert "--model" in opencode_cmd
    assert (
        opencode_cmd[opencode_cmd.index("--model") + 1]
        == "opencode-discovered-model"
    )

    sample_envelope.model = "openclaw/discovered-model"
    openclaw: OpenClawAdapter = OpenClawAdapter()
    openclaw_cmd: list[str] = openclaw.build_headless_command(sample_envelope)
    assert "--model" in openclaw_cmd
    assert (
        openclaw_cmd[openclaw_cmd.index("--model") + 1]
        == "openclaw/discovered-model"
    )


def test_adapter_list_available_models_mocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test adapters query subprocess directly to parse model lists.

    Parameters
    ------------
    monkeypatch: pytest.MonkeyPatch
        Pytest monkeypatch fixture.

    Returns
    --------
        None: NoneType object
            Asserts models are extracted from subprocess stdout.
    """
    import subprocess

    def fake_subprocess_run(cmd: list[str], **kwargs: Any) -> Any:
        """Simulate subprocess run for adapter model discovery.

        Parameters
        ------------
        cmd: list[str]
            Command arguments vector.
        **kwargs: Any
            Arbitrary keyword arguments passed to run.

        Returns
        --------
            Any: Any object
                CompletedProcess object matching requested binary.
        """
        bin_name: str = cmd[0]
        subcmd: str = cmd[1] if len(cmd) > 1 else ""
        if bin_name == "agy" and subcmd == "models":
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout=(
                    "Fetching available models...\n"
                    "gemini-4-argon-medium  Gemini 4 Argon\n"
                    "gemini-3.8-flash-high  Gemini 3.8 Flash\n"
                    "claude-opus-5-5-high   Claude Opus\n"
                ),
            )
        elif bin_name == "ollama" and subcmd == "list":
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout=(
                    "NAME ID SIZE MODIFIED\n"
                    "gemma4:26b 08ae7ec1744b 18 GB 5 weeks ago\n"
                    "kimi-k2.7-code:cloud 365c0bd3c000 4.7 GB 5 months ago\n"
                ),
            )
        elif bin_name == "openclaw" and subcmd == "models":
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout=(
                    "Model Input Ctx Local Auth Tags\n"
                    "ollama/gemma4:26b text+image 262k yes yes default\n"
                ),
            )
        return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="")

    monkeypatch.setattr(subprocess, "run", fake_subprocess_run)

    agy: AntigravityAdapter = AntigravityAdapter()
    agy_models: list[str] = agy.list_available_models()
    assert agy_models == [
        "gemini-4-argon-medium",
        "gemini-3.8-flash-high",
        "claude-opus-5-5-high",
    ]

    ollama: OllamaLocalAdapter = OllamaLocalAdapter()
    ollama_models: list[str] = ollama.list_available_models()
    assert ollama_models == ["gemma4:26b", "kimi-k2.7-code:cloud"]

    openclaw: OpenClawAdapter = OpenClawAdapter()
    monkeypatch.setattr(openclaw, "is_available", lambda: False)
    openclaw_models: list[str] = openclaw.list_available_models()
    assert openclaw_models == ["ollama/gemma4:26b"]

    reg: AdapterRegistry = AdapterRegistry()
    monkeypatch.setattr(agy, "is_available", lambda: True)
    monkeypatch.setattr(ollama, "is_available", lambda: True)
    reg.register_adapter("agy", agy)
    reg.register_adapter("ollama", ollama)

    all_models: dict[str, list[str]] = reg.list_all_models()
    assert "agy" in all_models
    assert "gemini-4-argon-medium" in all_models["agy"]
    assert "ollama" in all_models
    assert "gemma4:26b" in all_models["ollama"]
    assert "antigravity" not in all_models
    assert "ollama_local" not in all_models


def test_adapter_registry_deduplicates_aliases_in_list_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test registry returns canonical IDs without alias duplication.

    Parameters
    ------------
    monkeypatch: pytest.MonkeyPatch
        Pytest monkeypatch fixture.

    Returns
    --------
        None: NoneType object
            Asserts antigravity and ollama_local do not appear in available list.
    """
    reg: AdapterRegistry = AdapterRegistry()
    for adapter in reg._adapters.values():
        monkeypatch.setattr(adapter, "is_available", lambda: True)

    available: list[str] = reg.list_available()
    assert "agy" in available
    assert "ollama" in available
    assert "codex" in available
    assert "openclaw" in available
    assert "opencode" in available
    assert "antigravity" not in available
    assert "ollama_local" not in available

