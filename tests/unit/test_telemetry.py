"""Unit tests for Unified TelemetryTap, Stream Normalizer, and Circuit Breakers.

Tests streaming thinking tag parsing across chunk boundaries, multi-vendor stream
normalization, token pricing and cost tracking, and circuit breaker guardrails
(max_node_tokens, max_workflow_cost_usd, consecutive tool failures) with SQLite
WAL Blackboard state escalation (Milestone 3).
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import pytest

from neuri.core.blackboard import Blackboard
from neuri.core.config import BudgetConfig
from neuri.core.schemas import (
    NeuriTaskEnvelope,
    RemoteArtifact,
    SanitizedNeuroHeader,
    TaskNode,
    TaskState,
    TelemetryEvent,
)
from neuri.core.telemetry import (
    BlackboardBreakerCoordinator,
    CircuitBreakerPolicy,
    CircuitBreakerTripped,
    ConsecutiveToolFailureLimitExceeded,
    ModelPricing,
    ModelPricingTable,
    NodeTokenLimitExceeded,
    NormalizedStreamResult,
    ParsedStreamChunk,
    ParserState,
    StreamEventNormalizer,
    StreamingThinkingParser,
    TelemetryConstants,
    TelemetryTap,
    TokenCostTracker,
    WorkflowCostLimitExceeded,
)


@pytest.fixture
def blackboard_instance(tmp_path: Path) -> Blackboard:
    """Provide an initialized Blackboard instance in a temporary directory.

    Parameters
    ------------
    tmp_path: Path
        Pytest temporary directory fixture.

    Returns
    --------
        Blackboard: Blackboard instance
            Initialized SQLite WAL Blackboard object.
    """
    db_file: Path = tmp_path / "telemetry_test.db"
    bb: Blackboard = Blackboard(db_file)
    return bb


@pytest.fixture
def sample_task_node_fixture(
    sample_neuro_header: SanitizedNeuroHeader,
) -> TaskNode:
    """Provide a canonical TaskNode fixture for telemetry testing.

    Parameters
    ------------
    sample_neuro_header: SanitizedNeuroHeader
        Sanitized metadata header fixture.

    Returns
    --------
        TaskNode: TaskNode instance
            Canonical task node in RUNNING state.
    """
    artifact: RemoteArtifact = RemoteArtifact(
        artifact_id="art-telem-01",
        uri="hpc-cluster:///data/sub-01/anat/sub-01_T1w.nii.gz",
        host="hpc-cluster",
        posix_path="/data/sub-01/anat/sub-01_T1w.nii.gz",
        modality="T1w",
        space="MNI152NLin2009cAsym",
        bids_entities={"sub": "01", "datatype": "anat", "suffix": "T1w"},
        sha256_header="a" * 64,
        size_bytes=1048576,
        header_summary=sample_neuro_header,
        created_at=datetime.now(timezone.utc),
    )
    envelope: NeuriTaskEnvelope = NeuriTaskEnvelope(
        workflow_id="wf-telem-01",
        node_id="node-telem-01",
        agent_role="neuroimaging_specialist",
        harness_id="agy",
        execution_mode="headless_json",
        system_prompt="Test system prompt",
        task_instruction="Execute test pipeline step",
        input_artifacts=[artifact],
        max_tokens_budget=64000,
        max_cost_usd=2.0,
        attempt_number=1,
        max_retries=2,
    )
    node: TaskNode = TaskNode(
        node_id="node-telem-01",
        workflow_id="wf-telem-01",
        agent_role="neuroimaging_specialist",
        harness_id="agy",
        state=TaskState.RUNNING,
        attempt=1,
        max_retries=2,
        envelope=envelope,
    )
    return node


# ---------------------------------------------------------------------------
# Test Suite 1: StreamingThinkingParser
# ---------------------------------------------------------------------------


def test_thinking_parser_empty_chunk() -> None:
    """Test feeding an empty chunk produces empty deltas and outside state.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts empty deltas and outside state.
    """
    parser: StreamingThinkingParser = StreamingThinkingParser()
    chunk: ParsedStreamChunk = parser.feed("")
    assert chunk.thinking_delta == ""
    assert chunk.content_delta == ""
    assert chunk.is_thinking is False
    assert parser.is_inside_thinking is False


def test_thinking_parser_clean_text_only() -> None:
    """Test text without thinking tags passes directly through to content.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts all text appears in content_delta and clean_text.
    """
    parser: StreamingThinkingParser = StreamingThinkingParser()
    chunk: ParsedStreamChunk = parser.feed("Hello neuroscience researcher!")
    assert chunk.thinking_delta == ""
    assert chunk.content_delta == "Hello neuroscience researcher!"
    assert chunk.is_thinking is False
    assert parser.get_clean_text() == "Hello neuroscience researcher!"
    assert parser.get_thinking_text() == ""


def test_thinking_parser_isolated_thinking_block() -> None:
    """Test extracting an enclosed thinking block and surrounding text.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts clean separation of thinking and visible content.
    """
    parser: StreamingThinkingParser = StreamingThinkingParser()
    raw: str = "Prefix <thinking>analyzing BIDS structure</thinking> Postfix"
    chunk: ParsedStreamChunk = parser.feed(raw)
    assert chunk.thinking_delta == "analyzing BIDS structure"
    assert chunk.content_delta == "Prefix  Postfix"
    assert chunk.is_thinking is False
    assert parser.get_thinking_text() == "analyzing BIDS structure"
    assert parser.get_clean_text() == "Prefix  Postfix"
    assert parser.is_thinking_closed() is True


def test_thinking_parser_split_across_opening_tag() -> None:
    """Test opening tag split across multiple incoming stream chunks.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts opening tag buffer resolves cleanly without leakage.
    """
    parser: StreamingThinkingParser = StreamingThinkingParser()
    c1: ParsedStreamChunk = parser.feed("Start <thin")
    assert c1.content_delta == "Start "
    assert c1.thinking_delta == ""
    assert c1.is_thinking is False

    c2: ParsedStreamChunk = parser.feed("king>reasoning trace</thinking>End")
    assert c2.thinking_delta == "reasoning trace"
    assert c2.content_delta == "End"
    assert c2.is_thinking is False
    assert parser.get_thinking_text() == "reasoning trace"
    assert parser.get_clean_text() == "Start End"


def test_thinking_parser_split_across_closing_tag() -> None:
    """Test closing tag split across multiple incoming stream chunks.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts closing tag buffer resolves cleanly without leakage.
    """
    parser: StreamingThinkingParser = StreamingThinkingParser()
    c1: ParsedStreamChunk = parser.feed("<thinking>deep thought</think")
    assert c1.thinking_delta == "deep thought"
    assert c1.content_delta == ""
    assert c1.is_thinking is True

    c2: ParsedStreamChunk = parser.feed("ing>final answer")
    assert c2.thinking_delta == ""
    assert c2.content_delta == "final answer"
    assert c2.is_thinking is False
    assert parser.get_thinking_text() == "deep thought"
    assert parser.get_clean_text() == "final answer"


def test_thinking_parser_multiple_thinking_blocks() -> None:
    """Test handling sequential thinking blocks in stream.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts multiple blocks are accumulated cleanly.
    """
    parser: StreamingThinkingParser = StreamingThinkingParser()
    parser.feed("Step 1: <thinking>checking t1w</thinking> ok. ")
    parser.feed("Step 2: <thinking>checking bet</thinking> done.")
    assert parser.get_thinking_text() == "checking t1wchecking bet"
    assert parser.get_clean_text() == "Step 1:  ok. Step 2:  done."


def test_thinking_parser_unclosed_tag_flushed_at_eof() -> None:
    """Test unclosed thinking tag buffers are preserved when flushed at EOF.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts buffered text flushes to thinking without character loss.
    """
    parser: StreamingThinkingParser = StreamingThinkingParser()
    parser.feed("<thinking>in-flight hypothesis")
    flushed: ParsedStreamChunk = parser.flush()
    assert flushed.thinking_delta == ""
    assert parser.get_thinking_text() == "in-flight hypothesis"


def test_thinking_parser_reset_restores_clean_state() -> None:
    """Test reset method returns parser to initial outside state.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts reset clears buffers, state, and accumulated texts.
    """
    parser: StreamingThinkingParser = StreamingThinkingParser()
    parser.feed("<thinking>in progress")
    assert parser.is_inside_thinking is True
    parser.reset()
    assert parser.is_inside_thinking is False
    assert parser.get_thinking_text() == ""
    assert parser.get_clean_text() == ""


def test_thinking_parser_case_insensitive_matching() -> None:
    """Test parser correctly matches uppercase tags in case-insensitive mode.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts uppercase tags match when case_sensitive is False.
    """
    parser: StreamingThinkingParser = StreamingThinkingParser(
        case_sensitive=False
    )
    c: ParsedStreamChunk = parser.feed(
        "<THINKING>upper reasoning</THINKING>output"
    )
    assert c.thinking_delta == "upper reasoning"
    assert c.content_delta == "output"


def test_thinking_parser_tuple_unpacking_and_indexing() -> None:
    """Test ParsedStreamChunk supports tuple unpacking and index operations.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts index and unpacking behavior for backward compatibility.
    """
    chunk: ParsedStreamChunk = ParsedStreamChunk(
        thinking_delta="t_delta", content_delta="c_delta", is_thinking=False
    )
    t, c = chunk
    assert t == "t_delta"
    assert c == "c_delta"
    assert chunk[0] == "t_delta"
    assert chunk[1] == "c_delta"
    assert len(chunk) == 2


# ---------------------------------------------------------------------------
# Test Suite 2: ModelPricingTable & TokenCostTracker
# ---------------------------------------------------------------------------


def test_model_pricing_defaults() -> None:
    """Test default pricing retrieval for standard Tier-1 and Tier-2 harnesses.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts pricing rates match documented defaults.
    """
    table: ModelPricingTable = ModelPricingTable()
    agy_price: ModelPricing = table.get_pricing("agy")
    assert agy_price.input_cost_per_million == 3.00
    assert agy_price.output_cost_per_million == 15.00
    assert agy_price.cached_cost_per_million == 1.50
    assert agy_price.reasoning_cost_per_million == 15.00

    codex_price: ModelPricing = table.get_pricing("codex")
    assert codex_price.input_cost_per_million == 2.50
    assert codex_price.output_cost_per_million == 10.00


def test_model_pricing_custom_registration() -> None:
    """Test registering and overriding pricing rates for custom models.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts custom rates are stored and retrieved accurately.
    """
    table: ModelPricingTable = ModelPricingTable()
    custom: ModelPricing = ModelPricing(
        input_cost_per_million=5.00,
        output_cost_per_million=20.00,
        cached_cost_per_million=2.50,
        reasoning_cost_per_million=20.00,
    )
    table.register_pricing("custom-neuro-llm", custom)
    retrieved: ModelPricing = table.get_pricing("custom-neuro-llm")
    assert retrieved.input_cost_per_million == 5.00
    assert retrieved.output_cost_per_million == 20.00


def test_model_pricing_cost_calculation() -> None:
    """Test mathematical precision of USD cost calculation across token types.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts calculated USD values match expected formulas.
    """
    table: ModelPricingTable = ModelPricingTable()
    # agy rates: 3.00 input, 15.00 output, 1.50 cached, 15.00 reasoning per 1M
    cost: float = table.calculate_cost(
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        cached_tokens=1_000_000,
        reasoning_tokens=1_000_000,
        harness_or_model="agy",
    )
    expected: float = 3.00 + 15.00 + 1.50 + 15.00
    assert cost == pytest.approx(expected, abs=1e-5)


def test_model_pricing_zero_cost_local_ollama() -> None:
    """Test local Ollama executions incur exactly zero USD cost.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts local execution cost evaluates to zero.
    """
    table: ModelPricingTable = ModelPricingTable()
    cost: float = table.calculate_cost(
        input_tokens=500_000,
        output_tokens=100_000,
        cached_tokens=50_000,
        reasoning_tokens=20_000,
        harness_or_model="ollama_local",
    )
    assert cost == 0.0


def test_token_cost_tracker_incremental_recording() -> None:
    """Test incremental accumulation of tokens and USD costs per node.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts incremental additions aggregate correctly.
    """
    tracker: TokenCostTracker = TokenCostTracker()
    cost1: float = tracker.record_usage(
        node_id="node-1",
        input_tokens=1000,
        output_tokens=500,
        harness_id="agy",
    )
    assert cost1 > 0.0
    assert tracker.get_node_tokens("node-1") == 1500

    cost2: float = tracker.record_usage(
        node_id="node-1",
        input_tokens=2000,
        output_tokens=1000,
        harness_id="agy",
    )
    assert cost2 > cost1
    assert tracker.get_node_tokens("node-1") == 4500


def test_token_cost_tracker_cumulative_recording() -> None:
    """Test cumulative snapshot mode replaces previous node usage.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts snapshot replaces previous tally rather than summing.
    """
    tracker: TokenCostTracker = TokenCostTracker()
    tracker.record_usage(
        node_id="node-1",
        input_tokens=1000,
        output_tokens=500,
        harness_id="agy",
        is_cumulative=True,
    )
    assert tracker.get_node_tokens("node-1") == 1500

    tracker.record_usage(
        node_id="node-1",
        input_tokens=1200,
        output_tokens=600,
        harness_id="agy",
        is_cumulative=True,
    )
    assert tracker.get_node_tokens("node-1") == 1800


def test_token_cost_tracker_explicit_cost_override() -> None:
    """Test pre-computed vendor cost overrides table calculation.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts explicit cost value is preserved directly.
    """
    tracker: TokenCostTracker = TokenCostTracker()
    cost: float = tracker.record_usage(
        node_id="node-1",
        input_tokens=100,
        output_tokens=50,
        explicit_cost_usd=0.045,
    )
    assert cost == 0.045
    assert tracker.get_node_cost("node-1") == 0.045


def test_token_cost_tracker_workflow_aggregation() -> None:
    """Test aggregating tokens and costs across multiple distinct nodes.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts workflow totals reflect sum of all member nodes.
    """
    tracker: TokenCostTracker = TokenCostTracker()
    tracker.record_usage(
        node_id="node-1", input_tokens=1000, output_tokens=500, harness_id="agy"
    )
    tracker.record_usage(
        node_id="node-2", input_tokens=2000, output_tokens=800, harness_id="agy"
    )
    assert tracker.get_workflow_tokens() == 4300
    assert tracker.get_workflow_cost() > 0.0


def test_token_cost_tracker_node_and_all_reset() -> None:
    """Test resetting individual node metrics and clearing entire workflow.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts resets zero out the appropriate metric state.
    """
    tracker: TokenCostTracker = TokenCostTracker()
    tracker.record_usage(node_id="node-1", input_tokens=1000, output_tokens=500)
    tracker.record_usage(node_id="node-2", input_tokens=2000, output_tokens=800)

    tracker.reset_node("node-1")
    assert tracker.get_node_tokens("node-1") == 0
    assert tracker.get_node_tokens("node-2") == 2800

    tracker.reset_all()
    assert tracker.get_workflow_tokens() == 0
    assert tracker.get_workflow_cost() == 0.0


# ---------------------------------------------------------------------------
# Test Suite 3: CircuitBreakerPolicy
# ---------------------------------------------------------------------------


def test_circuit_breaker_node_tokens_within_limit() -> None:
    """Test token check passes when consumption is strictly below threshold.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts no exception is raised.
    """
    policy: CircuitBreakerPolicy = CircuitBreakerPolicy()
    # Default limit is 64000
    policy.check_node_tokens("node-1", 50000)


def test_circuit_breaker_node_tokens_exceeded() -> None:
    """Test NodeTokenLimitExceeded raised when token consumption hits ceiling.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts NodeTokenLimitExceeded is raised with metric details.
    """
    policy: CircuitBreakerPolicy = CircuitBreakerPolicy()
    with pytest.raises(NodeTokenLimitExceeded) as exc_info:
        policy.check_node_tokens("node-1", 64000)

    err: NodeTokenLimitExceeded = exc_info.value
    assert err.node_id == "node-1"
    assert err.metric == "tokens"
    assert err.limit == 64000.0
    assert err.current == 64000.0


def test_circuit_breaker_workflow_cost_within_limit() -> None:
    """Test cost check passes when USD cost is strictly below threshold.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts no exception is raised.
    """
    policy: CircuitBreakerPolicy = CircuitBreakerPolicy()
    # Default limit is $10.00
    policy.check_workflow_cost("node-1", 8.50)


def test_circuit_breaker_workflow_cost_exceeded() -> None:
    """Test WorkflowCostLimitExceeded raised when cost reaches ceiling.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts WorkflowCostLimitExceeded is raised with limit details.
    """
    policy: CircuitBreakerPolicy = CircuitBreakerPolicy()
    with pytest.raises(WorkflowCostLimitExceeded) as exc_info:
        policy.check_workflow_cost("node-1", 10.05)

    err: WorkflowCostLimitExceeded = exc_info.value
    assert err.node_id == "node-1"
    assert err.metric == "cost"
    assert err.limit == 10.00
    assert err.current == 10.05


def test_circuit_breaker_consecutive_tool_failure_limit() -> None:
    """Test consecutive identical tool failure breaker trips at threshold (3).

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts ConsecutiveToolFailureLimitExceeded raised on 3rd failure.
    """
    policy: CircuitBreakerPolicy = CircuitBreakerPolicy()
    policy.record_tool_call("node-1", "mri_convert", success=False)
    policy.record_tool_call("node-1", "mri_convert", success=False)

    with pytest.raises(ConsecutiveToolFailureLimitExceeded) as exc_info:
        policy.record_tool_call(
            "node-1",
            "mri_convert",
            success=False,
            error_message="Invalid NIfTI header",
        )

    err: ConsecutiveToolFailureLimitExceeded = exc_info.value
    assert err.node_id == "node-1"
    assert err.tool_name == "mri_convert"
    assert err.limit == 3.0
    assert err.current == 3.0


def test_circuit_breaker_consecutive_tool_failure_reset_on_success() -> None:
    """Test successful tool call resets consecutive failure counter.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts success prevents breaker from tripping on subsequent failure.
    """
    policy: CircuitBreakerPolicy = CircuitBreakerPolicy()
    policy.record_tool_call("node-1", "bet", success=False)
    policy.record_tool_call("node-1", "bet", success=False)
    # Success resets counter
    policy.record_tool_call("node-1", "bet", success=True)
    # This should be failure 1, not 3
    policy.record_tool_call("node-1", "bet", success=False)


def test_circuit_breaker_consecutive_tool_failure_reset_on_different_tool() -> None:
    """Test failure of a different tool resets count for the first tool.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts tool change resets consecutive failure counter to 1.
    """
    policy: CircuitBreakerPolicy = CircuitBreakerPolicy()
    policy.record_tool_call("node-1", "bet", success=False)
    policy.record_tool_call("node-1", "bet", success=False)
    # Different tool fails
    policy.record_tool_call("node-1", "flirt", success=False)
    # flirt is at 1, bet counter is reset
    policy.record_tool_call("node-1", "flirt", success=False)
    # flirt is at 2, not 3


def test_circuit_breaker_custom_limits() -> None:
    """Test custom BudgetConfig overrides standard default limits.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts custom configuration parameters are respected.
    """
    cfg: BudgetConfig = BudgetConfig(
        max_node_tokens=1000,
        max_workflow_cost_usd=1.00,
        consecutive_failure_threshold=2,
    )
    policy: CircuitBreakerPolicy = CircuitBreakerPolicy(config=cfg)
    with pytest.raises(NodeTokenLimitExceeded):
        policy.check_node_tokens("node-1", 1000)

    with pytest.raises(WorkflowCostLimitExceeded):
        policy.check_workflow_cost("node-1", 1.00)

    policy.record_tool_call("node-1", "recon-all", success=False)
    with pytest.raises(ConsecutiveToolFailureLimitExceeded):
        policy.record_tool_call("node-1", "recon-all", success=False)


# ---------------------------------------------------------------------------
# Test Suite 4: BlackboardBreakerCoordinator
# ---------------------------------------------------------------------------


def test_coordinator_handles_node_token_limit_exceeded(
    blackboard_instance: Blackboard,
    sample_task_node_fixture: TaskNode,
) -> None:
    """Test coordinator updates Blackboard node state to WAITING_OPERATOR.

    Parameters
    ------------
    blackboard_instance: Blackboard
        Persistent SQLite test blackboard fixture.
    sample_task_node_fixture: TaskNode
        Active task node fixture.

    Returns
    --------
        None: NoneType object
            Asserts state transition, diagnostic feedback, and event logging.
    """
    bb: Blackboard = blackboard_instance
    bb.create_workflow(
        workflow_id="wf-telem-01",
        description="Test workflow for telemetry coordination",
    )
    bb.register_node(sample_task_node_fixture)

    coordinator: BlackboardBreakerCoordinator = BlackboardBreakerCoordinator(bb)
    exc: NodeTokenLimitExceeded = NodeTokenLimitExceeded(
        reason="Token budget 64000 reached",
        node_id="node-telem-01",
        limit=64000.0,
        current=64001.0,
    )

    ev: TelemetryEvent = coordinator.handle_breaker_trip(
        exc=exc,
        workflow_id="wf-telem-01",
        harness_id="agy",
        current_tokens=64001,
        current_cost_usd=1.92,
    )

    assert ev.event_type == "circuit_breaker"
    assert ev.node_id == "node-telem-01"

    node: TaskNode | None = bb.get_node("node-telem-01")
    assert node is not None
    assert node.state == TaskState.WAITING_OPERATOR
    assert node.diagnostic_feedback is not None
    assert "Token budget 64000 reached" in node.diagnostic_feedback


def test_coordinator_handles_workflow_cost_limit_exceeded(
    blackboard_instance: Blackboard,
    sample_task_node_fixture: TaskNode,
) -> None:
    """Test coordinator handles workflow cost trip by pausing active node.

    Parameters
    ------------
    blackboard_instance: Blackboard
        Persistent SQLite test blackboard fixture.
    sample_task_node_fixture: TaskNode
        Active task node fixture.

    Returns
    --------
        None: NoneType object
            Asserts node transition to WAITING_OPERATOR on cost breach.
    """
    bb: Blackboard = blackboard_instance
    bb.create_workflow(
        workflow_id="wf-telem-01",
        description="Test workflow for cost coordination",
    )
    bb.register_node(sample_task_node_fixture)

    coordinator: BlackboardBreakerCoordinator = BlackboardBreakerCoordinator(bb)
    exc: WorkflowCostLimitExceeded = WorkflowCostLimitExceeded(
        reason="Workflow cost $10.00 reached",
        node_id="node-telem-01",
        limit=10.0,
        current=10.05,
    )

    coordinator.handle_breaker_trip(
        exc=exc,
        workflow_id="wf-telem-01",
        harness_id="agy",
        current_tokens=50000,
        current_cost_usd=10.05,
    )

    node: TaskNode | None = bb.get_node("node-telem-01")
    assert node is not None
    assert node.state == TaskState.WAITING_OPERATOR


# ---------------------------------------------------------------------------
# Test Suite 5: StreamEventNormalizer
# ---------------------------------------------------------------------------


def test_normalizer_plain_text() -> None:
    """Test normalizer extracts clean content and thinking from plain strings.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts plain text processing and thinking isolation.
    """
    normalizer: StreamEventNormalizer = StreamEventNormalizer(
        workflow_id="wf-1", node_id="node-1", harness_id="agy"
    )
    res: NormalizedStreamResult = normalizer.normalize_chunk(
        "Normal content <thinking>pondering</thinking> more content"
    )
    assert res.content_delta == "Normal content  more content"
    assert len(res.events) == 1
    assert res.events[0].event_type == "thinking_delta"
    assert res.events[0].thinking_text == "pondering"


def test_normalizer_session_start_json() -> None:
    """Test normalizer updates context on session_start NDJSON event.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts workflow and node context are updated.
    """
    normalizer: StreamEventNormalizer = StreamEventNormalizer()
    payload: str = json.dumps(
        {
            "event": "session_start",
            "workflow_id": "wf-custom",
            "node_id": "node-custom",
            "harness": "codex",
        }
    )
    res: NormalizedStreamResult = normalizer.normalize_chunk(payload)
    assert len(res.events) == 0
    assert normalizer._workflow_id == "wf-custom"
    assert normalizer._node_id == "node-custom"
    assert normalizer._harness_id == "codex"


def test_normalizer_tool_lifecycle_json() -> None:
    """Test normalizer processes tool_lifecycle NDJSON event into TelemetryEvent.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts tool status, name, and duration are captured.
    """
    normalizer: StreamEventNormalizer = StreamEventNormalizer(
        workflow_id="wf-1", node_id="node-1", harness_id="agy"
    )
    payload: str = json.dumps(
        {
            "type": "tool_lifecycle",
            "tool_name": "fsl_bet",
            "tool_host": "hpc-01",
            "tool_status": "completed",
            "duration_ms": 450,
        }
    )
    res: NormalizedStreamResult = normalizer.normalize_chunk(payload)
    assert len(res.events) == 1
    ev: TelemetryEvent = res.events[0]
    assert ev.event_type == "tool_lifecycle"
    assert ev.tool_name == "fsl_bet"
    assert ev.tool_host == "hpc-01"
    assert ev.tool_status == "completed"
    assert ev.duration_ms == 450


def test_normalizer_token_usage_json() -> None:
    """Test normalizer parses token usage event into TelemetryEvent.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts input, output, cached, and reasoning tokens are recorded.
    """
    normalizer: StreamEventNormalizer = StreamEventNormalizer(
        workflow_id="wf-1", node_id="node-1", harness_id="agy"
    )
    payload: str = json.dumps(
        {
            "type": "token_usage",
            "input_tokens": 1200,
            "cached_tokens": 400,
            "reasoning_tokens": 200,
            "output_tokens": 300,
            "cost_usd": 0.0085,
        }
    )
    res: NormalizedStreamResult = normalizer.normalize_chunk(payload)
    assert len(res.events) == 1
    ev: TelemetryEvent = res.events[0]
    assert ev.event_type == "token_usage"
    assert ev.input_tokens == 1200
    assert ev.cached_tokens == 400
    assert ev.reasoning_tokens == 200
    assert ev.output_tokens == 300
    assert ev.estimated_cost_usd == 0.0085


def test_normalizer_circuit_breaker_json() -> None:
    """Test normalizer captures vendor circuit breaker notification event.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts circuit_breaker TelemetryEvent is extracted.
    """
    normalizer: StreamEventNormalizer = StreamEventNormalizer(
        workflow_id="wf-1", node_id="node-1", harness_id="agy"
    )
    payload: str = json.dumps(
        {
            "type": "circuit_breaker",
            "breaker_reason": "Max output tokens reached",
        }
    )
    res: NormalizedStreamResult = normalizer.normalize_chunk(payload)
    assert len(res.events) == 1
    ev: TelemetryEvent = res.events[0]
    assert ev.event_type == "circuit_breaker"
    assert ev.breaker_reason == "Max output tokens reached"


# ---------------------------------------------------------------------------
# Test Suite 6: TelemetryTap End-to-End
# ---------------------------------------------------------------------------


def test_telemetry_tap_plain_text_stream() -> None:
    """Test TelemetryTap processes sequential chunks of text with thinking tags.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts text and thinking deltas are accumulated cleanly.
    """
    tap: TelemetryTap = TelemetryTap(
        workflow_id="wf-tap-01",
        node_id="node-tap-01",
        harness_id="agy",
    )
    e1: list[TelemetryEvent] = tap.process_chunk("Hello! <thin")
    assert len(e1) == 0

    e2: list[TelemetryEvent] = tap.process_chunk("king>Analyzing subject data")
    assert len(e2) == 1
    assert e2[0].event_type == "thinking_delta"
    assert e2[0].thinking_text == "Analyzing subject data"

    e3: list[TelemetryEvent] = tap.process_chunk("</thinking> All set!")
    assert tap.get_thinking_text() == "Analyzing subject data"
    assert tap.get_clean_text() == "Hello!  All set!"


def test_telemetry_tap_ndjson_stream_processing() -> None:
    """Test TelemetryTap processes mixed NDJSON events from harness stream.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts tool lifecycle and token usage events are captured.
    """
    tap: TelemetryTap = TelemetryTap(
        workflow_id="wf-tap-01",
        node_id="node-tap-01",
        harness_id="agy",
    )
    tool_event_json: str = json.dumps(
        {
            "event": "tool_lifecycle",
            "tool_name": "mrconvert",
            "tool_status": "completed",
            "duration_ms": 120,
        }
    )
    usage_event_json: str = json.dumps(
        {
            "event": "token_usage",
            "input_tokens": 2000,
            "output_tokens": 500,
            "cost_usd": 0.015,
        }
    )
    events: list[TelemetryEvent] = tap.process_chunk(
        f"{tool_event_json}\n{usage_event_json}"
    )
    assert len(events) == 2
    assert events[0].event_type == "tool_lifecycle"
    assert events[1].event_type == "token_usage"
    assert tap.get_total_tokens() == 2500
    assert tap.get_cost_usd() == 0.015


def test_telemetry_tap_trips_node_token_breaker() -> None:
    """Test TelemetryTap trips NodeTokenLimitExceeded when tokens breach limit.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts exception is raised and breaker tripped state is set.
    """
    tap: TelemetryTap = TelemetryTap(
        workflow_id="wf-tap-01",
        node_id="node-tap-01",
        max_node_tokens=5000,
    )
    with pytest.raises(NodeTokenLimitExceeded):
        tap.update_token_usage(
            input_tokens=4000,
            output_tokens=1001,
        )
    assert tap.is_breaker_tripped() is True


def test_telemetry_tap_trips_workflow_cost_breaker() -> None:
    """Test TelemetryTap trips WorkflowCostLimitExceeded when cost breaches limit.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts cost breach raises exception and trips breaker.
    """
    tap: TelemetryTap = TelemetryTap(
        workflow_id="wf-tap-01",
        node_id="node-tap-01",
        max_workflow_cost_usd=1.00,
    )
    with pytest.raises(WorkflowCostLimitExceeded):
        tap.update_token_usage(
            input_tokens=100,
            output_tokens=50,
            cost_usd=1.50,
        )
    assert tap.is_breaker_tripped() is True


def test_telemetry_tap_trips_consecutive_tool_failure_breaker() -> None:
    """Test TelemetryTap trips ConsecutiveToolFailureLimitExceeded at limit (3).

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts 3 consecutive failures of same tool trip breaker.
    """
    tap: TelemetryTap = TelemetryTap(
        workflow_id="wf-tap-01",
        node_id="node-tap-01",
        max_consecutive_tool_failures=3,
    )
    tap.record_tool_call("antsRegistration", success=False)
    tap.record_tool_call("antsRegistration", success=False)
    with pytest.raises(ConsecutiveToolFailureLimitExceeded):
        tap.record_tool_call("antsRegistration", success=False)
    assert tap.is_breaker_tripped() is True


def test_telemetry_tap_blackboard_integration(
    blackboard_instance: Blackboard,
    sample_task_node_fixture: TaskNode,
) -> None:
    """Test TelemetryTap auto-updates Blackboard when circuit breaker trips.

    Parameters
    ------------
    blackboard_instance: Blackboard
        Persistent SQLite test blackboard fixture.
    sample_task_node_fixture: TaskNode
        Active task node fixture.

    Returns
    --------
        None: NoneType object
            Asserts blackboard transition to WAITING_OPERATOR on trip.
    """
    bb: Blackboard = blackboard_instance
    bb.create_workflow(
        workflow_id="wf-telem-01",
        description="Blackboard integration test workflow",
    )
    bb.register_node(sample_task_node_fixture)

    tap: TelemetryTap = TelemetryTap(
        workflow_id="wf-telem-01",
        node_id="node-telem-01",
        harness_id="agy",
        max_node_tokens=1000,
        blackboard=bb,
    )

    with pytest.raises(NodeTokenLimitExceeded):
        tap.update_token_usage(input_tokens=800, output_tokens=300)

    node: TaskNode | None = bb.get_node("node-telem-01")
    assert node is not None
    assert node.state == TaskState.WAITING_OPERATOR
    assert node.diagnostic_feedback is not None
    assert "budget exceeded" in node.diagnostic_feedback


def test_telemetry_tap_reset_clears_metrics() -> None:
    """Test TelemetryTap reset restores zero tallies and clears breaker state.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Asserts reset restores initial clean telemetry state.
    """
    tap: TelemetryTap = TelemetryTap(
        workflow_id="wf-tap-01",
        node_id="node-tap-01",
    )
    tap.process_chunk("Some content <thinking>ponder</thinking>")
    tap.update_token_usage(input_tokens=500, output_tokens=200, cost_usd=0.005)
    tap.record_tool_call("bet", success=True)

    tap.reset()
    assert tap.get_total_tokens() == 0
    assert tap.get_cost_usd() == 0.0
    assert tap.get_thinking_text() == ""
    assert tap.get_clean_text() == ""
    assert tap.is_breaker_tripped() is False
    assert len(tap.get_events()) == 0
