"""Unified TelemetryTap and Circuit Breaker Subsystem for Neuri.

Provides multi-vendor stream normalization, chunk-boundary-resilient <thinking>
tag parsing, model token pricing and cost accumulation, and circuit breaker
guardrails (max_node_tokens, max_workflow_cost_usd, consecutive tool failures)
with SQLite WAL Blackboard state escalation.
"""

from collections.abc import Generator
from datetime import datetime, timezone
from enum import Enum
import json
from typing import Any, Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field

from neuri.core.blackboard import Blackboard
from neuri.core.config import BudgetConfig
from neuri.core.schemas import TaskState, TelemetryEvent


class TelemetryConstants:
    """Telemetry budget thresholds, XML tag names, and rate constants.

    Parameters
    ------------
    None

    Returns
    --------
        TelemetryConstants: TelemetryConstants class
            Constants container.
    """

    DEFAULT_MAX_NODE_TOKENS: int = 64000
    DEFAULT_MAX_WORKFLOW_COST_USD: float = 10.0
    DEFAULT_MAX_CONSECUTIVE_TOOL_FAILURES: int = 3
    DEFAULT_HARNESS_ID: str = "unknown"
    OPEN_THINKING_TAG: str = "<thinking>"
    CLOSE_THINKING_TAG: str = "</thinking>"


class ParserState(str, Enum):
    """Internal state machine states for streaming thinking tag parser.

    Parameters
    ------------
    None

    Returns
    --------
        ParserState: ParserState enum member
            Enumeration value representing the parser state.
    """

    OUTSIDE = "outside"
    THINKING = "thinking"


ThinkingParserState = ParserState


class NeuriException(Exception):
    """Base exception for all Neuri runtime, telemetry, and harness errors.

    Parameters
    ------------
    message: str
        Descriptive explanation of the error condition.

    Returns
    --------
        NeuriException: NeuriException instance
            Initialized base exception object.
    """

    def __init__(self, message: str) -> None:
        """Initialize base exception with explanatory message.

        Parameters
        ------------
        message: str
            Descriptive error message.

        Returns
        --------
            None: NoneType object
                Initializes exception state.
        """
        super().__init__(message)


class CircuitBreakerTripped(NeuriException):
    """Exception raised when a resource ceiling or fault threshold is exceeded.

    Parameters
    ------------
    reason: str
        Human-readable explanation of circuit breaker trip.
    node_id: str
        Identifier of task node.
    metric: str
        Metric category causing trip. Defaults to 'unknown'.
    limit: float
        Configured budget threshold. Defaults to 0.0.
    current: float
        Observed value. Defaults to 0.0.
    metric_name: str | None
        Alternative alias for metric. Defaults to None.
    threshold: float | None
        Alternative alias for limit. Defaults to None.
    current_value: float | None
        Alternative alias for current. Defaults to None.

    Returns
    --------
        CircuitBreakerTripped: CircuitBreakerTripped instance
            Constructed exception object.
    """

    def __init__(
        self,
        reason: str,
        node_id: str,
        metric: str = "unknown",
        limit: float = 0.0,
        current: float = 0.0,
        metric_name: str | None = None,
        threshold: float | None = None,
        current_value: float | None = None,
    ) -> None:
        """Initialize circuit breaker exception with reason and metrics.

        Parameters
        ------------
        reason: str
            Human-readable explanation of circuit breaker trip.
        node_id: str
            Identifier of task node.
        metric: str
            Metric category causing trip. Defaults to 'unknown'.
        limit: float
            Configured budget threshold. Defaults to 0.0.
        current: float
            Observed value. Defaults to 0.0.
        metric_name: str | None
            Alternative alias for metric. Defaults to None.
        threshold: float | None
            Alternative alias for limit. Defaults to None.
        current_value: float | None
            Alternative alias for current. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes exception attributes.
        """
        super().__init__(
            f"Circuit breaker tripped on node '{node_id}': {reason}"
        )
        self.reason: str = reason
        self.node_id: str = node_id

        resolved_metric: str = (
            metric if metric != "unknown" or metric_name is None
            else metric_name
        )
        self.metric: str = resolved_metric
        self.metric_name: str = resolved_metric

        resolved_limit: float = (
            limit if limit != 0.0 or threshold is None else float(threshold)
        )
        self.limit: float = resolved_limit
        self.threshold: float = resolved_limit

        resolved_current: float = (
            current if current != 0.0 or current_value is None
            else float(current_value)
        )
        self.current: float = resolved_current
        self.current_value: float = resolved_current


class NodeTokenLimitExceeded(CircuitBreakerTripped):
    """Raised when task node token consumption exceeds budget limit.

    Parameters
    ------------
    reason: str
        Explanation of token limit breach.
    node_id: str
        Identifier of the task node.
    limit: float
        Configured token limit. Defaults to 0.0.
    current: float
        Observed token count. Defaults to 0.0.
    threshold: float | None
        Alternative alias for limit. Defaults to None.
    current_value: float | None
        Alternative alias for current. Defaults to None.

    Returns
    --------
        NodeTokenLimitExceeded: NodeTokenLimitExceeded instance
            Initialized exception object.
    """

    def __init__(
        self,
        reason: str,
        node_id: str,
        limit: float = 0.0,
        current: float = 0.0,
        threshold: float | None = None,
        current_value: float | None = None,
    ) -> None:
        """Initialize node token limit exception.

        Parameters
        ------------
        reason: str
            Explanation of token limit breach.
        node_id: str
            Identifier of task node.
        limit: float
            Configured token limit. Defaults to 0.0.
        current: float
            Observed token count. Defaults to 0.0.
        threshold: float | None
            Alternative alias for limit. Defaults to None.
        current_value: float | None
            Alternative alias for current. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes exception attributes.
        """
        resolved_limit: float = (
            limit if limit != 0.0 or threshold is None else float(threshold)
        )
        resolved_current: float = (
            current if current != 0.0 or current_value is None
            else float(current_value)
        )
        super().__init__(
            reason=reason,
            node_id=node_id,
            metric="tokens",
            limit=resolved_limit,
            current=resolved_current,
            metric_name="tokens",
            threshold=resolved_limit,
            current_value=resolved_current,
        )


class WorkflowCostLimitExceeded(CircuitBreakerTripped):
    """Raised when total workflow cost in USD exceeds budget ceiling.

    Parameters
    ------------
    reason: str
        Explanation of cost ceiling breach.
    node_id: str
        Identifier of active task node.
    limit: float
        Configured cost limit in USD. Defaults to 0.0.
    current: float
        Observed cumulative cost in USD. Defaults to 0.0.
    threshold: float | None
        Alternative alias for limit. Defaults to None.
    current_value: float | None
        Alternative alias for current. Defaults to None.

    Returns
    --------
        WorkflowCostLimitExceeded: WorkflowCostLimitExceeded instance
            Initialized exception object.
    """

    def __init__(
        self,
        reason: str,
        node_id: str,
        limit: float = 0.0,
        current: float = 0.0,
        threshold: float | None = None,
        current_value: float | None = None,
    ) -> None:
        """Initialize workflow cost limit exception.

        Parameters
        ------------
        reason: str
            Explanation of cost ceiling breach.
        node_id: str
            Identifier of task node.
        limit: float
            Configured cost limit in USD. Defaults to 0.0.
        current: float
            Observed cumulative cost in USD. Defaults to 0.0.
        threshold: float | None
            Alternative alias for limit. Defaults to None.
        current_value: float | None
            Alternative alias for current. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes exception attributes.
        """
        resolved_limit: float = (
            limit if limit != 0.0 or threshold is None else float(threshold)
        )
        resolved_current: float = (
            current if current != 0.0 or current_value is None
            else float(current_value)
        )
        super().__init__(
            reason=reason,
            node_id=node_id,
            metric="cost",
            limit=resolved_limit,
            current=resolved_current,
            metric_name="cost",
            threshold=resolved_limit,
            current_value=resolved_current,
        )


class ConsecutiveToolFailureLimitExceeded(CircuitBreakerTripped):
    """Raised when the identical tool fails consecutively up to limit.

    Parameters
    ------------
    reason: str
        Explanation of consecutive failure breach.
    node_id: str
        Identifier of active task node.
    tool_name: str
        Name of the failing tool.
    limit: float
        Consecutive failure threshold. Defaults to 0.0.
    current: float
        Observed consecutive failure count. Defaults to 0.0.
    threshold: float | None
        Alternative alias for limit. Defaults to None.
    current_value: float | None
        Alternative alias for current. Defaults to None.

    Returns
    --------
        ConsecutiveToolFailureLimitExceeded: Exception instance
            Initialized exception object.
    """

    def __init__(
        self,
        reason: str,
        node_id: str,
        tool_name: str,
        limit: float = 0.0,
        current: float = 0.0,
        threshold: float | None = None,
        current_value: float | None = None,
    ) -> None:
        """Initialize consecutive tool failure exception.

        Parameters
        ------------
        reason: str
            Explanation of consecutive failure breach.
        node_id: str
            Identifier of active task node.
        tool_name: str
            Name of failing tool.
        limit: float
            Consecutive failure threshold. Defaults to 0.0.
        current: float
            Observed consecutive failure count. Defaults to 0.0.
        threshold: float | None
            Alternative alias for limit. Defaults to None.
        current_value: float | None
            Alternative alias for current. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes exception attributes.
        """
        resolved_limit: float = (
            limit if limit != 0.0 or threshold is None else float(threshold)
        )
        resolved_current: float = (
            current if current != 0.0 or current_value is None
            else float(current_value)
        )
        super().__init__(
            reason=reason,
            node_id=node_id,
            metric="tool_consecutive_failures",
            limit=resolved_limit,
            current=resolved_current,
            metric_name="consecutive_failures",
            threshold=resolved_limit,
            current_value=resolved_current,
        )
        self.tool_name: str = tool_name


class ModelPricing(BaseModel):
    """Token pricing rates per 1,000,000 tokens in USD.

    Parameters
    ------------
    input_cost_per_million: float
        Cost in USD per 1,000,000 prompt input tokens. Defaults to 3.00.
    output_cost_per_million: float
        Cost in USD per 1,000,000 completion output tokens. Defaults to 15.00.
    cached_cost_per_million: float
        Cost in USD per 1,000,000 prompt cache read tokens. Defaults to 1.50.
    reasoning_cost_per_million: float
        Cost in USD per 1,000,000 thinking/reasoning tokens. Defaults to 15.00.

    Returns
    --------
        ModelPricing: ModelPricing instance
            Constructed model pricing model.
    """

    model_config = ConfigDict(extra="forbid")

    input_cost_per_million: float = Field(
        default=3.00,
        ge=0.0,
        description="Cost in USD per 1M prompt input tokens",
    )
    output_cost_per_million: float = Field(
        default=15.00,
        ge=0.0,
        description="Cost in USD per 1M completion output tokens",
    )
    cached_cost_per_million: float = Field(
        default=1.50,
        ge=0.0,
        description="Cost in USD per 1M prompt cache read tokens",
    )
    reasoning_cost_per_million: float = Field(
        default=15.00,
        ge=0.0,
        description="Cost in USD per 1M reasoning tokens",
    )


class ModelPricingTable:
    """Registry and calculator for model token pricing rates.

    Encapsulates standard pricing rates for Tier-1 harnesses (Antigravity,
    Codex), Tier-2 harnesses (OpenCode, OpenClaw, Ollama), and custom models.
    Guarantees zero module-level globals.

    Parameters
    ------------
    custom_pricing: dict[str, ModelPricing] | None
        Optional dictionary of custom pricing overrides by harness/model name.
        Defaults to None.

    Returns
    --------
        ModelPricingTable: ModelPricingTable instance
            Constructed model pricing table registry.
    """

    ONE_MILLION: float = 1_000_000.0

    DEFAULT_RATES: dict[str, dict[str, float]] = {
        "default": {
            "input": 3.00,
            "output": 15.00,
            "cached": 1.50,
            "reasoning": 15.00,
        },
        "agy": {
            "input": 3.00,
            "output": 15.00,
            "cached": 1.50,
            "reasoning": 15.00,
        },
        "antigravity": {
            "input": 3.00,
            "output": 15.00,
            "cached": 1.50,
            "reasoning": 15.00,
        },
        "codex": {
            "input": 2.50,
            "output": 10.00,
            "cached": 1.25,
            "reasoning": 10.00,
        },
        "opencode": {
            "input": 3.00,
            "output": 15.00,
            "cached": 1.50,
            "reasoning": 15.00,
        },
        "openclaw": {
            "input": 3.00,
            "output": 15.00,
            "cached": 1.50,
            "reasoning": 15.00,
        },
        "ollama": {
            "input": 0.00,
            "output": 0.00,
            "cached": 0.00,
            "reasoning": 0.00,
        },
        "ollama_local": {
            "input": 0.00,
            "output": 0.00,
            "cached": 0.00,
            "reasoning": 0.00,
        },
    }

    def __init__(
        self, custom_pricing: dict[str, ModelPricing] | None = None
    ) -> None:
        """Initialize pricing table with built-in rates and custom overrides.

        Parameters
        ------------
        custom_pricing: dict[str, ModelPricing] | None
            Optional dictionary of custom pricing overrides. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes internal rates dictionary.
        """
        self._pricing_map: dict[str, ModelPricing] = {}
        for key, rates in self.DEFAULT_RATES.items():
            self._pricing_map[key] = ModelPricing(
                input_cost_per_million=rates["input"],
                output_cost_per_million=rates["output"],
                cached_cost_per_million=rates["cached"],
                reasoning_cost_per_million=rates["reasoning"],
            )
        if custom_pricing is not None:
            for custom_key, custom_val in custom_pricing.items():
                self._pricing_map[custom_key.lower()] = custom_val

    def get_pricing(self, harness_or_model: str) -> ModelPricing:
        """Retrieve model pricing rates for a given harness or model name.

        Parameters
        ------------
        harness_or_model: str
            Harness identifier or model name.

        Returns
        --------
            ModelPricing: ModelPricing object
                Active pricing model rates.
        """
        normalized_key: str = harness_or_model.strip().lower()
        pricing: ModelPricing = self._pricing_map.get(
            normalized_key, self._pricing_map["default"]
        )
        return pricing

    def register_pricing(
        self, harness_or_model: str, pricing: ModelPricing
    ) -> None:
        """Register or override pricing rates for a harness or model.

        Parameters
        ------------
        harness_or_model: str
            Target harness or model name.
        pricing: ModelPricing
            Configured ModelPricing instance.

        Returns
        --------
            None: NoneType object
                Updates internal pricing map.
        """
        normalized_key: str = harness_or_model.strip().lower()
        self._pricing_map[normalized_key] = pricing

    def calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
        reasoning_tokens: int = 0,
        harness_or_model: str = "default",
    ) -> float:
        """Calculate estimated cost in USD for token consumption breakdown.

        Parameters
        ------------
        input_tokens: int
            Count of prompt input tokens.
        output_tokens: int
            Count of completion output tokens.
        cached_tokens: int
            Count of cached prompt tokens. Defaults to 0.
        reasoning_tokens: int
            Count of reasoning/thinking tokens. Defaults to 0.
        harness_or_model: str
            Harness or model identifier. Defaults to 'default'.

        Returns
        --------
            float: float object
                Calculated cost in USD rounded to 6 decimal places.
        """
        pricing: ModelPricing = self.get_pricing(harness_or_model)
        input_cost: float = (
            input_tokens * pricing.input_cost_per_million
        ) / self.ONE_MILLION
        output_cost: float = (
            output_tokens * pricing.output_cost_per_million
        ) / self.ONE_MILLION
        cached_cost: float = (
            cached_tokens * pricing.cached_cost_per_million
        ) / self.ONE_MILLION
        reasoning_cost: float = (
            reasoning_tokens * pricing.reasoning_cost_per_million
        ) / self.ONE_MILLION

        total_cost: float = round(
            input_cost + output_cost + cached_cost + reasoning_cost, 6
        )
        return total_cost


class TokenCostTracker:
    """Tracks cumulative token usage and estimated USD costs per node and workflow.

    Provides granular aggregation for prompt, completion, cache, and thinking
    tokens, calculating real-time costs using ModelPricingTable.

    Parameters
    ------------
    pricing_table: ModelPricingTable | None
        Pricing table used for cost estimation. Defaults to None.

    Returns
    --------
        TokenCostTracker: TokenCostTracker instance
            Constructed token and cost tracker.
    """

    def __init__(
        self, pricing_table: ModelPricingTable | None = None
    ) -> None:
        """Initialize tracker with zeroed accumulators and pricing table.

        Parameters
        ------------
        pricing_table: ModelPricingTable | None
            Pricing table to use. Defaults to default table if None.

        Returns
        --------
            None: NoneType object
                Initializes tracking state.
        """
        self._pricing_table: ModelPricingTable = (
            pricing_table
            if pricing_table is not None
            else ModelPricingTable()
        )
        self._node_input_tokens: dict[str, int] = {}
        self._node_output_tokens: dict[str, int] = {}
        self._node_cached_tokens: dict[str, int] = {}
        self._node_reasoning_tokens: dict[str, int] = {}
        self._node_cost_usd: dict[str, float] = {}

    def record_usage(
        self,
        node_id: str,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
        reasoning_tokens: int = 0,
        harness_id: str = "default",
        explicit_cost_usd: float | None = None,
        is_cumulative: bool = False,
    ) -> float:
        """Record token usage for a node and return the updated node cost.

        Parameters
        ------------
        node_id: str
            Target node identifier.
        input_tokens: int
            Input tokens observed.
        output_tokens: int
            Output tokens observed.
        cached_tokens: int
            Cached tokens observed. Defaults to 0.
        reasoning_tokens: int
            Reasoning tokens observed. Defaults to 0.
        harness_id: str
            Harness identifier for pricing calculation. Defaults to 'default'.
        explicit_cost_usd: float | None
            Pre-computed USD cost from vendor if available. Defaults to None.
        is_cumulative: bool
            Whether incoming counts are cumulative snapshots. Defaults to False.

        Returns
        --------
            float: float object
                Updated cumulative cost for the specified node in USD.
        """
        if is_cumulative:
            self._node_input_tokens[node_id] = input_tokens
            self._node_output_tokens[node_id] = output_tokens
            self._node_cached_tokens[node_id] = cached_tokens
            self._node_reasoning_tokens[node_id] = reasoning_tokens
        else:
            self._node_input_tokens[node_id] = (
                self._node_input_tokens.get(node_id, 0) + input_tokens
            )
            self._node_output_tokens[node_id] = (
                self._node_output_tokens.get(node_id, 0) + output_tokens
            )
            self._node_cached_tokens[node_id] = (
                self._node_cached_tokens.get(node_id, 0) + cached_tokens
            )
            self._node_reasoning_tokens[node_id] = (
                self._node_reasoning_tokens.get(node_id, 0) + reasoning_tokens
            )

        if explicit_cost_usd is not None and explicit_cost_usd > 0.0:
            if is_cumulative:
                self._node_cost_usd[node_id] = explicit_cost_usd
            else:
                self._node_cost_usd[node_id] = (
                    self._node_cost_usd.get(node_id, 0.0) + explicit_cost_usd
                )
        else:
            computed_cost: float = self._pricing_table.calculate_cost(
                input_tokens=self._node_input_tokens[node_id],
                output_tokens=self._node_output_tokens[node_id],
                cached_tokens=self._node_cached_tokens[node_id],
                reasoning_tokens=self._node_reasoning_tokens[node_id],
                harness_or_model=harness_id,
            )
            self._node_cost_usd[node_id] = computed_cost

        cost_val: float = self._node_cost_usd[node_id]
        return cost_val

    def get_node_tokens(self, node_id: str) -> int:
        """Get total tokens (input + output + reasoning) for a given node.

        Parameters
        ------------
        node_id: str
            Target node identifier.

        Returns
        --------
            int: integer object
                Total token count consumed by the node.
        """
        total: int = (
            self._node_input_tokens.get(node_id, 0)
            + self._node_output_tokens.get(node_id, 0)
            + self._node_reasoning_tokens.get(node_id, 0)
        )
        return total

    def get_node_cost(self, node_id: str) -> float:
        """Get cumulative cost in USD for a given node.

        Parameters
        ------------
        node_id: str
            Target node identifier.

        Returns
        --------
            float: float object
                Cumulative node cost in USD.
        """
        cost: float = self._node_cost_usd.get(node_id, 0.0)
        return cost

    def get_workflow_tokens(self) -> int:
        """Get total cumulative tokens consumed across all nodes in workflow.

        Parameters
        ------------
        None

        Returns
        --------
            int: integer object
                Total cumulative tokens across all recorded nodes.
        """
        total: int = 0
        for node_id in self._node_input_tokens:
            total += self.get_node_tokens(node_id)
        return total

    def get_workflow_cost(self) -> float:
        """Get total cumulative cost in USD across all nodes in workflow.

        Parameters
        ------------
        None

        Returns
        --------
            float: float object
                Total cumulative cost across all recorded nodes in USD.
        """
        total: float = sum(self._node_cost_usd.values())
        cost_rounded: float = round(total, 6)
        return cost_rounded

    def reset_node(self, node_id: str) -> None:
        """Reset token and cost tallies for a single node.

        Parameters
        ------------
        node_id: str
            Target node identifier.

        Returns
        --------
            None: NoneType object
                Clears node metrics.
        """
        self._node_input_tokens.pop(node_id, None)
        self._node_output_tokens.pop(node_id, None)
        self._node_cached_tokens.pop(node_id, None)
        self._node_reasoning_tokens.pop(node_id, None)
        self._node_cost_usd.pop(node_id, None)

    def reset_all(self) -> None:
        """Reset all tracked token and cost metrics across all nodes.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Clears all metrics.
        """
        self._node_input_tokens.clear()
        self._node_output_tokens.clear()
        self._node_cached_tokens.clear()
        self._node_reasoning_tokens.clear()
        self._node_cost_usd.clear()


class ParsedStreamChunk(BaseModel):
    """Normalized chunk output separating thinking trace from visible content.

    Parameters
    ------------
    thinking_delta: str
        Extracted reasoning trace characters in this chunk. Defaults to "".
    content_delta: str
        Visible assistant message characters in this chunk. Defaults to "".
    is_thinking: bool
        Whether parser is currently inside a thinking block. Defaults to False.

    Returns
    --------
        ParsedStreamChunk: ParsedStreamChunk instance
            Constructed chunk model.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    thinking_delta: str = ""
    content_delta: str = ""
    is_thinking: bool = False

    def __iter__(self) -> Generator[str, None, None]:
        """Support tuple unpacking (thinking_delta, content_delta).

        Parameters
        ------------
        None

        Returns
        --------
            Generator[str, None, None]: generator object
                Yields thinking delta and content delta strings.
        """
        yield self.thinking_delta
        yield self.content_delta

    def __getitem__(self, index: int) -> str:
        """Support index access for tuple compatibility.

        Parameters
        ------------
        index: int
            Index 0 for thinking_delta, 1 for content_delta.

        Returns
        --------
            str: string object
                Delta string at index.
        """
        if index == 0:
            val: str = self.thinking_delta
            return val
        if index == 1:
            val = self.content_delta
            return val
        raise IndexError(f"Index {index} out of range for ParsedStreamChunk")

    def __len__(self) -> int:
        """Return length for tuple unpacking.

        Parameters
        ------------
        None

        Returns
        --------
            int: integer object
                Length 2.
        """
        length: int = 2
        return length


class NormalizedStreamResult(BaseModel):
    """Result of normalizing a raw stream chunk or vendor event line.

    Parameters
    ------------
    events: list[TelemetryEvent]
        List of typed telemetry events extracted from the chunk.
    content_delta: str
        Clean visible content text to pass through to the assistant turn.
    is_thinking: bool
        Whether parser is currently inside a reasoning trace.

    Returns
    --------
        NormalizedStreamResult: NormalizedStreamResult instance
            Constructed normalized result model.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    events: list[TelemetryEvent] = Field(default_factory=list)
    content_delta: str = ""
    is_thinking: bool = False


class StreamingThinkingParser:
    """Robust streaming state machine parsing <thinking> across chunk splits.

    Maintains tag buffers across arbitrary chunk splits (e.g. '<thin', 'king>',
    '</think', 'ing>') and sliding suffix matching to guarantee zero character
    loss and zero tag leakage.
    """

    def __init__(
        self, tag_name: str = "thinking", case_sensitive: bool = False
    ) -> None:
        """Initialize streaming thinking parser.

        Parameters
        ------------
        tag_name: str
            XML tag name to isolate. Defaults to 'thinking'.
        case_sensitive: bool
            Whether tag matching is case-sensitive. Defaults to False.

        Returns
        --------
            None: NoneType object
                Initializes parser state and buffers.
        """
        self._tag_name: str = tag_name
        self._open_tag: str = f"<{tag_name}>"
        self._close_tag: str = f"</{tag_name}>"
        self._case_sensitive: bool = case_sensitive
        self._state: ParserState = ParserState.OUTSIDE
        self._tag_buffer: str = ""
        self._accumulated_thinking: list[str] = []
        self._accumulated_clean: list[str] = []

    def feed(self, chunk: str) -> ParsedStreamChunk:
        """Process incremental text chunk and extract thinking and clean deltas.

        Parameters
        ------------
        chunk: str
            Raw incremental chunk of text.

        Returns
        --------
            ParsedStreamChunk: ParsedStreamChunk instance
                Extracted thinking delta, content delta, and thinking state.
        """
        thinking_parts: list[str] = []
        content_parts: list[str] = []

        for char in chunk:
            if self._state == ParserState.OUTSIDE:
                candidate: str = self._tag_buffer + char
                target: str = self._open_tag
                cand_cmp: str = (
                    candidate if self._case_sensitive else candidate.lower()
                )
                tgt_cmp: str = (
                    target if self._case_sensitive else target.lower()
                )

                if tgt_cmp.startswith(cand_cmp):
                    if len(candidate) == len(target):
                        self._state = ParserState.THINKING
                        self._tag_buffer = ""
                    else:
                        self._tag_buffer = candidate
                else:
                    found_suffix: str = ""
                    for idx in range(1, len(candidate)):
                        suffix: str = candidate[idx:]
                        suf_cmp: str = (
                            suffix if self._case_sensitive else suffix.lower()
                        )
                        if tgt_cmp.startswith(suf_cmp):
                            found_suffix = suffix
                            break

                    emit_len: int = len(candidate) - len(found_suffix)
                    content_parts.append(candidate[:emit_len])
                    self._tag_buffer = found_suffix

            elif self._state == ParserState.THINKING:
                candidate = self._tag_buffer + char
                target = self._close_tag
                cand_cmp = (
                    candidate if self._case_sensitive else candidate.lower()
                )
                tgt_cmp = (
                    target if self._case_sensitive else target.lower()
                )

                if tgt_cmp.startswith(cand_cmp):
                    if len(candidate) == len(target):
                        self._state = ParserState.OUTSIDE
                        self._tag_buffer = ""
                    else:
                        self._tag_buffer = candidate
                else:
                    found_suffix = ""
                    for idx in range(1, len(candidate)):
                        suffix = candidate[idx:]
                        suf_cmp = (
                            suffix if self._case_sensitive else suffix.lower()
                        )
                        if tgt_cmp.startswith(suf_cmp):
                            found_suffix = suffix
                            break

                    emit_len = len(candidate) - len(found_suffix)
                    thinking_parts.append(candidate[:emit_len])
                    self._tag_buffer = found_suffix

        t_delta: str = "".join(thinking_parts)
        c_delta: str = "".join(content_parts)
        if t_delta:
            self._accumulated_thinking.append(t_delta)
        if c_delta:
            self._accumulated_clean.append(c_delta)

        res: ParsedStreamChunk = ParsedStreamChunk(
            thinking_delta=t_delta,
            content_delta=c_delta,
            is_thinking=(self._state == ParserState.THINKING),
        )
        return res

    def flush(self) -> ParsedStreamChunk:
        """Flush remaining buffered tag characters at end of stream.

        Parameters
        ------------
        None

        Returns
        --------
            ParsedStreamChunk: ParsedStreamChunk instance
                Flushed characters routed according to current parser state.
        """
        flushed_thinking: str = ""
        flushed_content: str = ""

        if self._tag_buffer:
            if self._state == ParserState.THINKING:
                flushed_thinking = self._tag_buffer
                self._accumulated_thinking.append(flushed_thinking)
            else:
                flushed_content = self._tag_buffer
                self._accumulated_clean.append(flushed_content)
            self._tag_buffer = ""

        res: ParsedStreamChunk = ParsedStreamChunk(
            thinking_delta=flushed_thinking,
            content_delta=flushed_content,
            is_thinking=(self._state == ParserState.THINKING),
        )
        return res

    def get_thinking_text(self) -> str:
        """Return consolidated thinking text accumulated across all chunks.

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                Full thinking text.
        """
        full_thinking: str = "".join(self._accumulated_thinking)
        return full_thinking

    def get_clean_text(self) -> str:
        """Return consolidated clean text outside thinking tags.

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                Full clean content text.
        """
        full_clean: str = "".join(self._accumulated_clean)
        return full_clean

    def is_thinking_closed(self) -> bool:
        """Check if thinking tag was cleanly closed.

        Parameters
        ------------
        None

        Returns
        --------
            bool: boolean object
                True if currently outside thinking tag with empty buffer.
        """
        is_closed: bool = (
            self._state == ParserState.OUTSIDE and not self._tag_buffer
        )
        return is_closed

    def reset(self) -> None:
        """Reset parser state and buffers to initial clean state.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Clears buffers and resets state to OUTSIDE.
        """
        self._state = ParserState.OUTSIDE
        self._tag_buffer = ""
        self._accumulated_thinking.clear()
        self._accumulated_clean.clear()

    @property
    def is_inside_thinking(self) -> bool:
        """Check whether parser is currently within a thinking block.

        Parameters
        ------------
        None

        Returns
        --------
            bool: boolean object
                True if active state is THINKING, False otherwise.
        """
        active: bool = self._state == ParserState.THINKING
        return active


ThinkingParser = StreamingThinkingParser


class StreamEventNormalizer:
    """Normalizes multi-vendor stream payloads into canonical TelemetryEvents.

    Parses JSON lines from Antigravity and Codex CLI, processes raw string
    chunks, extracts thinking traces, and formats standardized TelemetryEvents.
    """

    def __init__(
        self,
        workflow_id: str = "wf_default",
        node_id: str = "node_default",
        harness_id: str = "generic",
    ) -> None:
        """Initialize stream event normalizer.

        Parameters
        ------------
        workflow_id: str
            Associated workflow identifier. Defaults to 'wf_default'.
        node_id: str
            Associated task node identifier. Defaults to 'node_default'.
        harness_id: str
            Harness backend identifier. Defaults to 'generic'.

        Returns
        --------
            None: NoneType object
                Initializes parser and identifier context.
        """
        self._workflow_id: str = workflow_id
        self._node_id: str = node_id
        self._harness_id: str = harness_id
        self._parser: StreamingThinkingParser = StreamingThinkingParser()

    def set_context(
        self, workflow_id: str, node_id: str, harness_id: str
    ) -> None:
        """Update workflow and node context for subsequent events.

        Parameters
        ------------
        workflow_id: str
            Target workflow identifier.
        node_id: str
            Target node identifier.
        harness_id: str
            Target harness identifier.

        Returns
        --------
            None: NoneType object
                Updates internal context properties.
        """
        self._workflow_id = workflow_id
        self._node_id = node_id
        self._harness_id = harness_id

    def normalize_chunk(self, raw_chunk: str) -> NormalizedStreamResult:
        """Normalize a stream chunk into TelemetryEvents and clean content.

        Parameters
        ------------
        raw_chunk: str
            Raw string chunk (NDJSON line or plain text).

        Returns
        --------
            NormalizedStreamResult: NormalizedStreamResult instance
                Aggregated telemetry events and clean visible content delta.
        """
        emitted_events: list[TelemetryEvent] = []
        content_deltas: list[str] = []

        lines: list[str] = raw_chunk.splitlines(keepends=True)
        if not lines:
            lines = [raw_chunk]

        for line in lines:
            stripped: str = line.strip()
            if stripped.startswith("{") and stripped.endswith("}"):
                try:
                    payload: dict[str, Any] = json.loads(stripped)
                    if isinstance(payload, dict):
                        line_res: NormalizedStreamResult = (
                            self._normalize_json_event(payload)
                        )
                        emitted_events.extend(line_res.events)
                        if line_res.content_delta:
                            content_deltas.append(line_res.content_delta)
                        continue
                except (json.JSONDecodeError, ValueError):
                    pass

            parsed: ParsedStreamChunk = self._parser.feed(line)
            if parsed.thinking_delta:
                ev: TelemetryEvent = TelemetryEvent(
                    event_id=f"tevt_{uuid.uuid4().hex[:16]}",
                    workflow_id=self._workflow_id,
                    node_id=self._node_id,
                    harness_id=self._harness_id,
                    event_type="thinking_delta",
                    thinking_text=parsed.thinking_delta,
                )
                emitted_events.append(ev)
            if parsed.content_delta:
                content_deltas.append(parsed.content_delta)

        result: NormalizedStreamResult = NormalizedStreamResult(
            events=emitted_events,
            content_delta="".join(content_deltas),
            is_thinking=self._parser.is_inside_thinking,
        )
        return result

    def _normalize_json_event(
        self, payload: dict[str, Any]
    ) -> NormalizedStreamResult:
        """Normalize an individual vendor JSON event dictionary.

        Parameters
        ------------
        payload: dict[str, Any]
            Decoded JSON event dictionary.

        Returns
        --------
            NormalizedStreamResult: NormalizedStreamResult instance
                Normalized event result with typed TelemetryEvents.
        """
        events: list[TelemetryEvent] = []
        content_delta: str = ""

        raw_event: str = str(payload.get("event", ""))
        raw_type: str = str(payload.get("type", ""))

        wf_id: str = str(payload.get("workflow_id") or self._workflow_id)
        n_id: str = str(payload.get("node_id") or self._node_id)
        h_id: str = str(
            payload.get("harness")
            or payload.get("harness_id")
            or self._harness_id
        )

        ts_raw: Any = payload.get("timestamp")
        ts: datetime = datetime.now(timezone.utc)
        if isinstance(ts_raw, str):
            try:
                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            except ValueError:
                pass

        if raw_type in ("session_start",) or raw_event in (
            "start",
            "session.created",
        ):
            self.set_context(wf_id, n_id, h_id)

        elif raw_type in ("chunk",) or raw_event in (
            "chunk",
            "response.output_item.added",
            "response.text.delta",
        ):
            raw_content: str = str(payload.get("content") or "")
            parsed: ParsedStreamChunk = self._parser.feed(raw_content)
            if parsed.thinking_delta:
                events.append(
                    TelemetryEvent(
                        event_id=f"tevt_{uuid.uuid4().hex[:16]}",
                        workflow_id=wf_id,
                        node_id=n_id,
                        harness_id=h_id,
                        timestamp=ts,
                        event_type="thinking_delta",
                        thinking_text=parsed.thinking_delta,
                    )
                )
            content_delta = parsed.content_delta

        elif raw_type in ("tool_call",) or raw_event in (
            "tool_lifecycle",
            "tool.call.started",
            "tool.call.completed",
            "tool.call.failed",
        ):
            raw_status: str = str(
                payload.get("tool_status") or payload.get("status") or ""
            ).lower()
            status_lit: Literal["started", "completed", "failed"] | None = None
            if raw_status in ("started", "completed", "failed"):
                status_lit = raw_status  # type: ignore[assignment]

            events.append(
                TelemetryEvent(
                    event_id=f"tevt_{uuid.uuid4().hex[:16]}",
                    workflow_id=wf_id,
                    node_id=n_id,
                    harness_id=h_id,
                    timestamp=ts,
                    event_type="tool_lifecycle",
                    tool_name=payload.get("tool_name"),
                    tool_host=payload.get("tool_host"),
                    tool_status=status_lit,
                    duration_ms=payload.get("duration_ms"),
                )
            )

        elif raw_type in ("usage",) or raw_event in (
            "token_usage",
            "response.token_usage",
        ):
            cost_val: float = float(
                payload.get("cost_usd")
                or payload.get("estimated_cost_usd")
                or 0.0
            )
            events.append(
                TelemetryEvent(
                    event_id=f"tevt_{uuid.uuid4().hex[:16]}",
                    workflow_id=wf_id,
                    node_id=n_id,
                    harness_id=h_id,
                    timestamp=ts,
                    event_type="token_usage",
                    input_tokens=int(payload.get("input_tokens") or 0),
                    cached_tokens=int(payload.get("cached_tokens") or 0),
                    reasoning_tokens=int(payload.get("reasoning_tokens") or 0),
                    output_tokens=int(payload.get("output_tokens") or 0),
                    estimated_cost_usd=cost_val,
                )
            )

        elif raw_type in ("circuit_breaker",) or raw_event in (
            "circuit_breaker",
        ):
            events.append(
                TelemetryEvent(
                    event_id=f"tevt_{uuid.uuid4().hex[:16]}",
                    workflow_id=wf_id,
                    node_id=n_id,
                    harness_id=h_id,
                    timestamp=ts,
                    event_type="circuit_breaker",
                    breaker_reason=str(payload.get("breaker_reason") or ""),
                )
            )

        res: NormalizedStreamResult = NormalizedStreamResult(
            events=events,
            content_delta=content_delta,
            is_thinking=self._parser.is_inside_thinking,
        )
        return res

    def flush(self) -> NormalizedStreamResult:
        """Flush remaining buffered characters at the end of the stream.

        Parameters
        ------------
        None

        Returns
        --------
            NormalizedStreamResult: NormalizedStreamResult instance
                Final flushed telemetry events and content delta.
        """
        flushed: ParsedStreamChunk = self._parser.flush()
        events: list[TelemetryEvent] = []
        if flushed.thinking_delta:
            events.append(
                TelemetryEvent(
                    event_id=f"tevt_{uuid.uuid4().hex[:16]}",
                    workflow_id=self._workflow_id,
                    node_id=self._node_id,
                    harness_id=self._harness_id,
                    event_type="thinking_delta",
                    thinking_text=flushed.thinking_delta,
                )
            )

        res: NormalizedStreamResult = NormalizedStreamResult(
            events=events,
            content_delta=flushed.content_delta,
            is_thinking=self._parser.is_inside_thinking,
        )
        return res


class CircuitBreakerPolicy:
    """Enforces the three core Neuri circuit breaker guardrails.

    Monitors:
    1. Maximum node tokens (default 64,000).
    2. Maximum workflow cost in USD (default $10.00).
    3. Consecutive identical tool call failures (threshold 3).

    Parameters
    ------------
    config: BudgetConfig | None
        Budget configuration containing limits and thresholds. Defaults to None.

    Returns
    --------
        CircuitBreakerPolicy: CircuitBreakerPolicy instance
            Constructed policy enforcement engine.
    """

    def __init__(self, config: BudgetConfig | None = None) -> None:
        """Initialize policy with budget configuration thresholds.

        Parameters
        ------------
        config: BudgetConfig | None
            Budget configuration model. Defaults to standard BudgetConfig.

        Returns
        --------
            None: NoneType object
                Initializes breaker state and counters.
        """
        self._config: BudgetConfig = (
            config if config is not None else BudgetConfig()
        )
        self._last_failed_tool: str | None = None
        self._consecutive_failures: int = 0

    @property
    def max_node_tokens(self) -> int:
        """Configured ceiling for tokens consumed per node.

        Parameters
        ------------
        None

        Returns
        --------
            int: integer object
                Token threshold.
        """
        tokens_limit: int = self._config.max_node_tokens
        return tokens_limit

    @property
    def max_workflow_cost_usd(self) -> float:
        """Configured ceiling for total workflow cost in USD.

        Parameters
        ------------
        None

        Returns
        --------
            float: float object
                Cost threshold in USD.
        """
        cost_limit: float = self._config.max_workflow_cost_usd
        return cost_limit

    @property
    def consecutive_failure_threshold(self) -> int:
        """Configured consecutive failure count to trip breaker.

        Parameters
        ------------
        None

        Returns
        --------
            int: integer object
                Failure count threshold.
        """
        threshold_val: int = self._config.consecutive_failure_threshold
        return threshold_val

    def check_node_tokens(
        self,
        node_id: str,
        current_tokens: int,
        custom_limit: int | None = None,
    ) -> None:
        """Check if node token count exceeds configured threshold.

        Parameters
        ------------
        node_id: str
            Target node identifier.
        current_tokens: int
            Cumulative tokens consumed by the node.
        custom_limit: int | None
            Optional envelope-level budget limit override. Defaults to None.

        Returns
        --------
            None: NoneType object
                Passes if within budget, raises NodeTokenLimitExceeded if breached.
        """
        limit: int = (
            custom_limit if custom_limit is not None else self.max_node_tokens
        )
        if current_tokens >= limit:
            reason: str = (
                f"Node token budget exceeded: {current_tokens} >= {limit}"
            )
            raise NodeTokenLimitExceeded(
                reason=reason,
                node_id=node_id,
                limit=float(limit),
                current=float(current_tokens),
            )

    def check_workflow_cost(
        self,
        node_id: str,
        current_cost_usd: float,
        custom_limit: float | None = None,
    ) -> None:
        """Check if cumulative workflow cost exceeds configured USD ceiling.

        Parameters
        ------------
        node_id: str
            Active node identifier during evaluation.
        current_cost_usd: float
            Cumulative workflow cost in USD.
        custom_limit: float | None
            Optional workflow-level cost override. Defaults to None.

        Returns
        --------
            None: NoneType object
                Passes if within budget, raises WorkflowCostLimitExceeded if breached.
        """
        limit: float = (
            custom_limit
            if custom_limit is not None
            else self.max_workflow_cost_usd
        )
        if current_cost_usd >= limit:
            reason: str = (
                f"Workflow cost limit exceeded: "
                f"${current_cost_usd:.2f} >= ${limit:.2f}"
            )
            raise WorkflowCostLimitExceeded(
                reason=reason,
                node_id=node_id,
                limit=float(limit),
                current=float(current_cost_usd),
            )

    def record_tool_call(
        self,
        node_id: str,
        tool_name: str,
        success: bool,
        error_message: str | None = None,
    ) -> None:
        """Record tool call outcome and enforce consecutive failure breaker.

        Parameters
        ------------
        node_id: str
            Target node identifier.
        tool_name: str
            Canonical tool name invoked.
        success: bool
            Whether the tool call succeeded.
        error_message: str | None
            Optional tool error diagnostic. Defaults to None.

        Returns
        --------
            None: NoneType object
                Updates tracking state or raises
                ConsecutiveToolFailureLimitExceeded.
        """
        if success:
            if self._last_failed_tool == tool_name:
                self._consecutive_failures = 0
                self._last_failed_tool = None
            return

        if self._last_failed_tool == tool_name:
            self._consecutive_failures += 1
        else:
            self._last_failed_tool = tool_name
            self._consecutive_failures = 1

        if self._consecutive_failures >= self.consecutive_failure_threshold:
            limit: float = float(self.consecutive_failure_threshold)
            count: float = float(self._consecutive_failures)
            reason: str = (
                f"Consecutive failure limit reached for tool {tool_name}"
            )
            if error_message:
                reason += f": {error_message}"
            raise ConsecutiveToolFailureLimitExceeded(
                reason=reason,
                node_id=node_id,
                tool_name=tool_name,
                limit=limit,
                current=count,
            )

    def reset_tool_tracking(self) -> None:
        """Reset consecutive tool failure tracking state.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Clears tool failure tracking.
        """
        self._last_failed_tool = None
        self._consecutive_failures = 0


class BlackboardBreakerCoordinator:
    """Coordinates Blackboard state transitions when circuit breakers trip.

    Implements the core integration contract:
    1. Transitions task node state to TaskState.WAITING_OPERATOR.
    2. Appends structured diagnostic error feedback to Blackboard.
    3. Persists TelemetryEvent(event_type='circuit_breaker') into state.db.
    4. Updates workflow status to 'WAITING_OPERATOR'.

    Parameters
    ------------
    blackboard: Blackboard
        Persistent SQLite Blackboard instance.

    Returns
    --------
        BlackboardBreakerCoordinator: BlackboardBreakerCoordinator instance
            Constructed coordinator.
    """

    def __init__(self, blackboard: Blackboard) -> None:
        """Initialize coordinator with target Blackboard instance.

        Parameters
        ------------
        blackboard: Blackboard
            Target Blackboard instance.

        Returns
        --------
            None: NoneType object
                Initializes coordinator state.
        """
        self._blackboard: Blackboard = blackboard

    def handle_breaker_trip(
        self,
        exc: CircuitBreakerTripped,
        workflow_id: str,
        harness_id: str = "default",
        current_tokens: int = 0,
        current_cost_usd: float = 0.0,
    ) -> TelemetryEvent:
        """Handle a tripped breaker by transitioning node state and logging event.

        Parameters
        ------------
        exc: CircuitBreakerTripped
            The tripped circuit breaker exception.
        workflow_id: str
            Parent workflow identifier.
        harness_id: str
            Harness identifier. Defaults to 'default'.
        current_tokens: int
            Cumulative tokens consumed by the node at trip time. Defaults to 0.
        current_cost_usd: float
            Cumulative cost in USD at trip time. Defaults to 0.0.

        Returns
        --------
            TelemetryEvent: TelemetryEvent object
                The circuit breaker telemetry event persisted to the Blackboard.
        """
        feedback_entry: str = f"Circuit breaker tripped: {exc.reason}"
        summary: str = f"Paused in WAITING_OPERATOR: {exc.reason}"
        self._blackboard.update_node_state(
            node_id=exc.node_id,
            state=TaskState.WAITING_OPERATOR,
            diagnostic_feedback=feedback_entry,
            summary_result=summary,
        )

        event_id: str = f"cb_{uuid.uuid4().hex[:12]}"
        event: TelemetryEvent = TelemetryEvent(
            event_id=event_id,
            workflow_id=workflow_id,
            node_id=exc.node_id,
            harness_id=harness_id,
            event_type="circuit_breaker",
            breaker_reason=exc.reason,
            input_tokens=current_tokens,
            output_tokens=0,
            estimated_cost_usd=current_cost_usd,
        )
        self._blackboard.record_telemetry_event(event)

        try:
            self._blackboard.update_workflow_status(
                workflow_id=workflow_id,
                status="WAITING_OPERATOR",
                total_tokens=current_tokens,
                estimated_cost_usd=current_cost_usd,
            )
        except Exception:
            pass

        return event


class TelemetryTap:
    """Unified telemetry interceptor and circuit breaker guardrail manager.

    Parameters
    ------------
    workflow_id: str
        Parent workflow identifier.
    node_id: str
        Target task node identifier.
    harness_id: str
        Execution harness identifier. Defaults to 'unknown'.
    max_node_tokens: int
        Hard token budget ceiling for node. Defaults to 64000.
    max_workflow_cost_usd: float
        Hard USD cost budget ceiling for workflow. Defaults to 10.0.
    max_consecutive_tool_failures: int
        Consecutive identical tool failure ceiling. Defaults to 3.
    blackboard: Any | None
        Optional Blackboard state engine for event logging and escalation.
        Defaults to None.

    Returns
    --------
        TelemetryTap: TelemetryTap instance
            Constructed telemetry tap.
    """

    def __init__(
        self,
        workflow_id: str,
        node_id: str,
        harness_id: str = TelemetryConstants.DEFAULT_HARNESS_ID,
        max_node_tokens: int = TelemetryConstants.DEFAULT_MAX_NODE_TOKENS,
        max_workflow_cost_usd: float = (
            TelemetryConstants.DEFAULT_MAX_WORKFLOW_COST_USD
        ),
        max_consecutive_tool_failures: int = (
            TelemetryConstants.DEFAULT_MAX_CONSECUTIVE_TOOL_FAILURES
        ),
        blackboard: Any | None = None,
    ) -> None:
        """Initialize unified TelemetryTap interceptor.

        Parameters
        ------------
        workflow_id: str
            Parent workflow identifier.
        node_id: str
            Target task node identifier.
        harness_id: str
            Execution harness identifier. Defaults to 'unknown'.
        max_node_tokens: int
            Hard token budget ceiling for node. Defaults to 64000.
        max_workflow_cost_usd: float
            Hard USD cost budget ceiling for workflow. Defaults to 10.0.
        max_consecutive_tool_failures: int
            Consecutive identical tool failure ceiling. Defaults to 3.
        blackboard: Any | None
            Optional Blackboard state engine. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes internal states, accumulators, and breaker limits.
        """
        self.workflow_id: str = workflow_id
        self.node_id: str = node_id
        self.harness_id: str = harness_id
        self.max_node_tokens: int = max_node_tokens
        self.max_workflow_cost_usd: float = max_workflow_cost_usd
        self.max_consecutive_tool_failures: int = (
            max_consecutive_tool_failures
        )
        self._blackboard: Any | None = blackboard

        self._thinking_parser: StreamingThinkingParser = (
            StreamingThinkingParser()
        )
        self._pricing_table: ModelPricingTable = ModelPricingTable()

        self._input_tokens: int = 0
        self._output_tokens: int = 0
        self._cached_tokens: int = 0
        self._reasoning_tokens: int = 0
        self._cost_usd: float = 0.0

        self._tool_calls_total: int = 0
        self._tool_calls_succeeded: int = 0
        self._tool_calls_failed: int = 0
        self._consecutive_tool_failures: int = 0
        self._last_failed_tool: str | None = None

        self._breaker_tripped: bool = False
        self._breaker_reason: str | None = None
        self._events: list[TelemetryEvent] = []

    def process_chunk(self, chunk: str) -> list[TelemetryEvent]:
        """Process incoming raw chunk or NDJSON string and emit TelemetryEvents.

        Parameters
        ------------
        chunk: str
            Raw text stream chunk or NDJSON record.

        Returns
        --------
            list[TelemetryEvent]: list object
                List of normalized telemetry events generated.
        """
        emitted_events: list[TelemetryEvent] = []
        raw_lines: list[str] = chunk.splitlines(keepends=True)
        if not raw_lines:
            raw_lines = [chunk]

        for line in raw_lines:
            stripped: str = line.strip()
            if stripped.startswith("{") and stripped.endswith("}"):
                try:
                    record: dict[str, Any] = json.loads(stripped)
                    if isinstance(record, dict):
                        ev: TelemetryEvent | None = (
                            self._process_ndjson_record(record)
                        )
                        if ev is not None:
                            emitted_events.append(ev)
                        continue
                except (json.JSONDecodeError, ValueError):
                    pass

            self._process_text_chunk(line, emitted_events)

        return emitted_events

    def _process_text_chunk(
        self, text: str, out_events: list[TelemetryEvent]
    ) -> None:
        """Process raw text through thinking parser and emit thinking deltas.

        Parameters
        ------------
        text: str
            Raw text delta.
        out_events: list[TelemetryEvent]
            Accumulator list for emitted events.

        Returns
        --------
            None: NoneType object
                Appends events to accumulator.
        """
        parsed: ParsedStreamChunk = self._thinking_parser.feed(text)
        if parsed.thinking_delta:
            event: TelemetryEvent = TelemetryEvent(
                event_id=f"evt-{uuid.uuid4().hex[:12]}",
                workflow_id=self.workflow_id,
                node_id=self.node_id,
                harness_id=self.harness_id,
                event_type="thinking_delta",
                thinking_text=parsed.thinking_delta,
            )
            out_events.append(event)
            self._log_event(event)

    def _process_ndjson_record(
        self, record: dict[str, Any]
    ) -> TelemetryEvent | None:
        """Parse structured NDJSON record into canonical TelemetryEvent.

        Parameters
        ------------
        record: dict[str, Any]
            Deserialized JSON record from harness stdout stream.

        Returns
        --------
            TelemetryEvent | None: TelemetryEvent or None
                Normalized telemetry event or None if unhandled.
        """
        event_name: str = str(
            record.get("event") or record.get("type") or ""
        )
        result_event: TelemetryEvent | None = None

        if event_name in ("session_start", "start", "session.created"):
            if "workflow_id" in record:
                self.workflow_id = str(record["workflow_id"])
            if "node_id" in record:
                self.node_id = str(record["node_id"])
            if "harness" in record:
                self.harness_id = str(record["harness"])
            elif "harness_id" in record:
                self.harness_id = str(record["harness_id"])

        elif event_name in (
            "chunk", "response.output_item.added", "response.text.delta"
        ):
            raw_content: str = str(record.get("content", ""))
            parsed: ParsedStreamChunk = self._thinking_parser.feed(raw_content)
            if parsed.thinking_delta:
                result_event = TelemetryEvent(
                    event_id=f"evt-{uuid.uuid4().hex[:12]}",
                    workflow_id=self.workflow_id,
                    node_id=self.node_id,
                    harness_id=self.harness_id,
                    event_type="thinking_delta",
                    thinking_text=parsed.thinking_delta,
                )
                self._log_event(result_event)

        elif event_name in (
            "token_usage", "usage", "response.token_usage"
        ):
            in_tok: int = int(record.get("input_tokens", 0))
            out_tok: int = int(record.get("output_tokens", 0))
            cached_tok: int = int(record.get("cached_tokens", 0))
            reasoning_tok: int = int(record.get("reasoning_tokens", 0))
            cost_val: float = float(
                record.get("cost_usd")
                or record.get("estimated_cost_usd")
                or 0.0
            )

            is_cum: bool = (
                bool(record.get("is_cumulative", False))
                or self.harness_id in ("agy", "antigravity")
            )

            self.update_token_usage(
                input_tokens=in_tok,
                output_tokens=out_tok,
                cached_tokens=cached_tok,
                reasoning_tokens=reasoning_tok,
                cost_usd=cost_val,
                is_cumulative=is_cum,
            )

            result_event = TelemetryEvent(
                event_id=f"evt-{uuid.uuid4().hex[:12]}",
                workflow_id=self.workflow_id,
                node_id=self.node_id,
                harness_id=self.harness_id,
                event_type="token_usage",
                input_tokens=in_tok,
                output_tokens=out_tok,
                cached_tokens=cached_tok,
                reasoning_tokens=reasoning_tok,
                estimated_cost_usd=cost_val,
            )
            self._log_event(result_event)

        elif event_name in (
            "tool_lifecycle",
            "tool_call",
            "tool.call.started",
            "tool.call.completed",
            "tool.call.failed",
        ):
            tool_name: str = str(record.get("tool_name", "unknown"))
            tool_host: str = str(record.get("tool_host", "localhost"))
            status: str = str(
                record.get("tool_status") or record.get("status") or "completed"
            ).lower()
            duration_ms: int | None = (
                int(record["duration_ms"]) if "duration_ms" in record else None
            )

            if "failed" in event_name or status == "failed":
                norm_status: Literal["started", "completed", "failed"] = "failed"
                self.record_tool_call(
                    tool_name=tool_name,
                    success=False,
                    error_message=record.get("error"),
                    duration_ms=duration_ms,
                    tool_host=tool_host,
                )
            elif "started" in event_name or status == "started":
                norm_status = "started"
            else:
                norm_status = "completed"
                self.record_tool_call(
                    tool_name=tool_name,
                    success=True,
                    duration_ms=duration_ms,
                    tool_host=tool_host,
                )

            result_event = TelemetryEvent(
                event_id=f"evt-{uuid.uuid4().hex[:12]}",
                workflow_id=self.workflow_id,
                node_id=self.node_id,
                harness_id=self.harness_id,
                event_type="tool_lifecycle",
                tool_name=tool_name,
                tool_host=tool_host,
                tool_status=norm_status,
                duration_ms=duration_ms,
            )
            self._log_event(result_event)

        elif event_name == "circuit_breaker":
            reason: str = str(
                record.get("breaker_reason") or "Circuit breaker tripped"
            )
            metric_val: str = str(record.get("metric", "unknown"))
            limit_val: float = float(record.get("limit", 0.0))
            current_val: float = float(record.get("current", 0.0))

            exc_cls: type[CircuitBreakerTripped] = CircuitBreakerTripped
            if metric_val == "tokens":
                exc_cls = NodeTokenLimitExceeded
            elif metric_val in ("cost", "cost_usd"):
                exc_cls = WorkflowCostLimitExceeded
            elif metric_val in (
                "consecutive_failures", "tool_consecutive_failures"
            ):
                exc_cls = ConsecutiveToolFailureLimitExceeded

            self._trigger_breaker(
                reason=reason,
                metric=metric_val,
                limit=limit_val,
                current=current_val,
                exc_class=exc_cls,
            )

        return result_event

    def record_tool_call(
        self,
        tool_name: str,
        success: bool,
        error_message: str | None = None,
        duration_ms: int | None = None,
        tool_host: str = "localhost",
    ) -> None:
        """Record tool call outcome and enforce consecutive failure limit.

        Parameters
        ------------
        tool_name: str
            Name of executed tool.
        success: bool
            Whether execution succeeded.
        error_message: str | None
            Error diagnostic details if failed. Defaults to None.
        duration_ms: int | None
            Execution duration in milliseconds. Defaults to None.
        tool_host: str
            Host where tool executed. Defaults to 'localhost'.

        Returns
        --------
            None: NoneType object
                Updates tool counters and trips breaker if threshold met.
        """
        self._tool_calls_total += 1
        if success:
            self._tool_calls_succeeded += 1
            if self._last_failed_tool == tool_name:
                self._consecutive_tool_failures = 0
                self._last_failed_tool = None
        else:
            self._tool_calls_failed += 1
            if self._last_failed_tool == tool_name:
                self._consecutive_tool_failures += 1
            else:
                self._last_failed_tool = tool_name
                self._consecutive_tool_failures = 1

            if (
                self._consecutive_tool_failures
                >= self.max_consecutive_tool_failures
            ):
                reason: str = (
                    f"Consecutive failure limit reached for tool {tool_name}"
                )
                if error_message:
                    reason += f": {error_message}"
                self._trigger_breaker(
                    reason=reason,
                    metric="tool_consecutive_failures",
                    limit=float(self.max_consecutive_tool_failures),
                    current=float(self._consecutive_tool_failures),
                    exc_class=ConsecutiveToolFailureLimitExceeded,
                    tool_name=tool_name,
                )

    def check_breakers(
        self,
        node_id: str,
        current_tokens: int,
        current_cost: float,
    ) -> None:
        """Verify token and cost metrics against budget limits.

        Parameters
        ------------
        node_id: str
            Executing node identifier.
        current_tokens: int
            Current cumulative token count.
        current_cost: float
            Current cumulative USD cost.

        Returns
        --------
            None: NoneType object
                Raises CircuitBreakerTripped if any limit is met or exceeded.
        """
        if current_tokens >= self.max_node_tokens:
            reason: str = (
                f"Node token budget exceeded: {current_tokens} >= "
                f"{self.max_node_tokens}"
            )
            self._trigger_breaker(
                reason=reason,
                metric="tokens",
                limit=float(self.max_node_tokens),
                current=float(current_tokens),
                exc_class=NodeTokenLimitExceeded,
            )

        if current_cost >= self.max_workflow_cost_usd:
            reason = (
                f"Workflow cost budget exceeded: {current_cost} >= "
                f"{self.max_workflow_cost_usd}"
            )
            self._trigger_breaker(
                reason=reason,
                metric="cost",
                limit=float(self.max_workflow_cost_usd),
                current=float(current_cost),
                exc_class=WorkflowCostLimitExceeded,
            )

    def update_token_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
        reasoning_tokens: int = 0,
        cost_usd: float = 0.0,
        is_cumulative: bool = False,
    ) -> None:
        """Update accumulated token metrics and check circuit breakers.

        Parameters
        ------------
        input_tokens: int
            Input tokens observed.
        output_tokens: int
            Output tokens observed.
        cached_tokens: int
            Prompt cached tokens. Defaults to 0.
        reasoning_tokens: int
            Thinking tokens. Defaults to 0.
        cost_usd: float
            Cost in USD. Defaults to 0.0.
        is_cumulative: bool
            Whether incoming counts are cumulative snapshots. Defaults to False.

        Returns
        --------
            None: NoneType object
                Updates state and evaluates breakers.
        """
        if is_cumulative:
            self._input_tokens = input_tokens
            self._output_tokens = output_tokens
            self._cached_tokens = cached_tokens
            self._reasoning_tokens = reasoning_tokens
            if cost_usd > 0.0:
                self._cost_usd = cost_usd
            else:
                self._cost_usd = self._pricing_table.calculate_cost(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cached_tokens=cached_tokens,
                    reasoning_tokens=reasoning_tokens,
                    harness_or_model=self.harness_id,
                )
        else:
            self._input_tokens += input_tokens
            self._output_tokens += output_tokens
            self._cached_tokens += cached_tokens
            self._reasoning_tokens += reasoning_tokens
            if cost_usd > 0.0:
                self._cost_usd += cost_usd
            else:
                inc_cost: float = self._pricing_table.calculate_cost(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cached_tokens=cached_tokens,
                    reasoning_tokens=reasoning_tokens,
                    harness_or_model=self.harness_id,
                )
                self._cost_usd += inc_cost

        self._cost_usd = round(self._cost_usd, 6)
        total: int = self._input_tokens + self._output_tokens
        self.check_breakers(self.node_id, total, self._cost_usd)

    def _trigger_breaker(
        self,
        reason: str,
        metric: str,
        limit: float,
        current: float,
        exc_class: type[CircuitBreakerTripped] = CircuitBreakerTripped,
        tool_name: str | None = None,
    ) -> None:
        """Record breaker trip, update Blackboard state, and raise exception.

        Parameters
        ------------
        reason: str
            Trip explanation.
        metric: str
            Metric name ('tokens', 'cost', 'tool_consecutive_failures').
        limit: float
            Configured ceiling.
        current: float
            Observed value.
        exc_class: type[CircuitBreakerTripped]
            Exception class to instantiate and raise. Defaults to
            CircuitBreakerTripped.
        tool_name: str | None
            Name of failing tool if applicable. Defaults to None.

        Returns
        --------
            None: NoneType object
                Never returns normally; raises CircuitBreakerTripped subclass.
        """
        self._breaker_tripped = True
        self._breaker_reason = reason

        event: TelemetryEvent = TelemetryEvent(
            event_id=f"evt-brk-{uuid.uuid4().hex[:10]}",
            workflow_id=self.workflow_id,
            node_id=self.node_id,
            harness_id=self.harness_id,
            event_type="circuit_breaker",
            breaker_reason=reason,
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
            estimated_cost_usd=self._cost_usd,
        )
        self._log_event(event)

        if self._blackboard is not None:
            self._blackboard.update_node_state(
                self.node_id,
                TaskState.WAITING_OPERATOR,
                diagnostic_feedback=reason,
            )
            try:
                self._blackboard.update_workflow_status(
                    workflow_id=self.workflow_id,
                    status="WAITING_OPERATOR",
                    total_tokens=self.get_accumulated_tokens(),
                    estimated_cost_usd=self._cost_usd,
                )
            except Exception:
                pass

        if (
            issubclass(exc_class, ConsecutiveToolFailureLimitExceeded)
            and tool_name is not None
        ):
            raise ConsecutiveToolFailureLimitExceeded(
                reason=reason,
                node_id=self.node_id,
                tool_name=tool_name,
                limit=limit,
                current=current,
            )
        if issubclass(exc_class, NodeTokenLimitExceeded):
            raise NodeTokenLimitExceeded(
                reason=reason,
                node_id=self.node_id,
                limit=limit,
                current=current,
            )
        if issubclass(exc_class, WorkflowCostLimitExceeded):
            raise WorkflowCostLimitExceeded(
                reason=reason,
                node_id=self.node_id,
                limit=limit,
                current=current,
            )

        raise CircuitBreakerTripped(
            reason=reason,
            node_id=self.node_id,
            metric=metric,
            limit=limit,
            current=current,
        )

    def _log_event(self, event: TelemetryEvent) -> None:
        """Record event in memory and optionally in SQLite Blackboard.

        Parameters
        ------------
        event: TelemetryEvent
            Canonical telemetry event model.

        Returns
        --------
            None: NoneType object
                Appends to in-memory list and persists to database if present.
        """
        self._events.append(event)
        if self._blackboard is not None:
            self._blackboard.record_telemetry_event(event)

    def get_metrics(self) -> dict[str, Any]:
        """Retrieve aggregated metrics snapshot dictionary.

        Parameters
        ------------
        None

        Returns
        --------
            dict[str, Any]: dictionary object
                Metrics dictionary containing token, cost, tool, and breaker
                tallies.
        """
        metrics: dict[str, Any] = {
            "total_tokens": self.get_accumulated_tokens(),
            "input_tokens": self._input_tokens,
            "output_tokens": self._output_tokens,
            "cached_tokens": self._cached_tokens,
            "reasoning_tokens": self._reasoning_tokens,
            "cost_usd": self._cost_usd,
            "tool_calls_total": self._tool_calls_total,
            "tool_calls_succeeded": self._tool_calls_succeeded,
            "tool_calls_failed": self._tool_calls_failed,
            "consecutive_tool_failures": self._consecutive_tool_failures,
            "last_failed_tool": self._last_failed_tool,
            "breaker_tripped": self._breaker_tripped,
            "breaker_reason": self._breaker_reason,
        }
        return metrics

    def get_accumulated_tokens(self) -> int:
        """Return total tokens consumed (input + output).

        Parameters
        ------------
        None

        Returns
        --------
            int: integer object
                Total token count.
        """
        total: int = self._input_tokens + self._output_tokens
        return total

    def get_accumulated_cost(self) -> float:
        """Return estimated USD cost consumed.

        Parameters
        ------------
        None

        Returns
        --------
            float: float object
                Cost in USD.
        """
        cost: float = self._cost_usd
        return cost

    def get_thinking_text(self) -> str:
        """Return full accumulated thinking text.

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                Consolidated thinking string.
        """
        res: str = self._thinking_parser.get_thinking_text()
        return res

    def get_clean_text(self) -> str:
        """Return full accumulated clean text.

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                Consolidated clean content string.
        """
        res: str = self._thinking_parser.get_clean_text()
        return res

    def is_breaker_tripped(self) -> bool:
        """Check if any circuit breaker has tripped.

        Parameters
        ------------
        None

        Returns
        --------
            bool: boolean object
                True if breaker tripped, False otherwise.
        """
        tripped: bool = self._breaker_tripped
        return tripped

    def get_events(self) -> list[TelemetryEvent]:
        """Return shallow copy of all recorded telemetry events.

        Parameters
        ------------
        None

        Returns
        --------
            list[TelemetryEvent]: list object
                Recorded telemetry events.
        """
        events_copy: list[TelemetryEvent] = list(self._events)
        return events_copy

    def flush(self) -> list[TelemetryEvent]:
        """Flush thinking parser buffers and return any residual events.

        Parameters
        ------------
        None

        Returns
        --------
            list[TelemetryEvent]: list object
                Residual events generated on flush.
        """
        residual_events: list[TelemetryEvent] = []
        flushed: ParsedStreamChunk = self._thinking_parser.flush()
        if flushed.thinking_delta:
            event: TelemetryEvent = TelemetryEvent(
                event_id=f"evt-{uuid.uuid4().hex[:12]}",
                workflow_id=self.workflow_id,
                node_id=self.node_id,
                harness_id=self.harness_id,
                event_type="thinking_delta",
                thinking_text=flushed.thinking_delta,
            )
            residual_events.append(event)
            self._log_event(event)
        return residual_events

    def reset(self) -> None:
        """Reset all metric tallies, failure counters, and parser states.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Clears telemetry state.
        """
        self._thinking_parser.reset()
        self._input_tokens = 0
        self._output_tokens = 0
        self._cached_tokens = 0
        self._reasoning_tokens = 0
        self._cost_usd = 0.0

        self._tool_calls_total = 0
        self._tool_calls_succeeded = 0
        self._tool_calls_failed = 0
        self._consecutive_tool_failures = 0
        self._last_failed_tool = None

        self._breaker_tripped = False
        self._breaker_reason = None
        self._events.clear()


__all__: list[str] = [
    "BlackboardBreakerCoordinator",
    "CircuitBreakerPolicy",
    "CircuitBreakerTripped",
    "ConsecutiveToolFailureLimitExceeded",
    "ModelPricing",
    "ModelPricingTable",
    "NeuriException",
    "NodeTokenLimitExceeded",
    "NormalizedStreamResult",
    "ParsedStreamChunk",
    "ParserState",
    "StreamEventNormalizer",
    "StreamingThinkingParser",
    "TelemetryConstants",
    "TelemetryTap",
    "ThinkingParser",
    "ThinkingParserState",
    "TokenCostTracker",
    "WorkflowCostLimitExceeded",
]
