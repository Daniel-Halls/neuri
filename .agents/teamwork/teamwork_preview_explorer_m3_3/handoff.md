# Milestone 3 Architecture & Unit Test Plan Handoff Report

## 1. Observation

### 1.1 Existing System Contracts and Codebase Locations
1. **Pydantic Schemas (`src/neuri/core/schemas.py`)**:
   - `TelemetryEvent` (lines 1211–1346):
     ```python
     class TelemetryEvent(BaseModel):
         event_id: str
         workflow_id: str
         node_id: str
         harness_id: str
         timestamp: datetime
         event_type: Literal[
             "thinking_delta", "token_usage", "tool_lifecycle", "circuit_breaker"
         ]
         thinking_text: str | None = None
         input_tokens: int = 0
         cached_tokens: int = 0
         reasoning_tokens: int = 0
         output_tokens: int = 0
         estimated_cost_usd: float = 0.0
         tool_name: str | None = None
         tool_host: str | None = None
         tool_status: Literal["started", "completed", "failed"] | None = None
         duration_ms: int | None = None
         breaker_reason: str | None = None
     ```
     `model_config = ConfigDict(extra="forbid")` is enforced. All fields must strictly match this schema.
   - `TaskState` (lines 473–540): includes `RUNNING`, `WAITING_OPERATOR`, `COMPLETED`, `FAILED`, `CANCELLED`.
   - `TaskNode` (lines 916–1152): holds `node_id`, `workflow_id`, `state`, `attempt`, `max_retries`, `diagnostic_feedback` (list of strings).
   - `NeuriTaskEnvelope` (lines 542–760): contains `max_tokens_budget: int = 64000`, `max_cost_usd: float = 2.00`.

2. **SQLite WAL Blackboard (`src/neuri/core/blackboard.py`)**:
   - `update_node_state` (lines 1703–1850):
     ```python
     def update_node_state(
         self,
         node_id: str,
         state: TaskState,
         diagnostic_feedback: str | None = None,
         summary_result: str | None = None,
     ) -> None:
     ```
     Allows valid state transition from `RUNNING` -> `WAITING_OPERATOR` (lines 478–485) and appends `diagnostic_feedback`.
   - `record_telemetry_event` (lines 2509–2558):
     ```python
     def record_telemetry_event(self, event: TelemetryEvent) -> None:
     ```
     Inserts normalized telemetry events into the `telemetry_events` table in `.neuri/state.db`.
   - `list_telemetry_events` (lines 2559–2620): queries events by `workflow_id` and optional `node_id`.

3. **Stream Fixture Analysis (`tests/fixtures/`)**:
   - `agy_stream_sample.ndjson` (lines 2–5):
     ```json
     {"event": "chunk", "type": "chunk", "content": "<think", "timestamp": "2026-10-25T14:30:01Z"}
     {"event": "chunk", "type": "chunk", "content": "ing>Validating BIDS dataset structure...", "timestamp": "2026-10-25T14:30:02Z"}
     {"event": "chunk", "type": "chunk", "content": " All fields verified.</think", "timestamp": "2026-10-25T14:30:03Z"}
     {"event": "chunk", "type": "chunk", "content": "ing>BIDS structure for sub-01 is fully compliant...", "timestamp": "2026-10-25T14:30:04Z"}
     ```
     Observed split opening tag (`<think` + `ing>`) and split closing tag (`</think` + `ing>`) across chunk boundaries, followed immediately by clean content.
   - `agy_breaker_sample.ndjson` (lines 7–8):
     ```json
     {"event": "token_usage", "type": "usage", "input_tokens": 35000, "output_tokens": 12000, "reasoning_tokens": 22000, "cost_usd": 1.45, "timestamp": "2026-10-25T14:35:06Z"}
     {"event": "circuit_breaker", "type": "circuit_breaker", "breaker_reason": "Node token budget exceeded", "metric": "tokens", "limit": 64000.0, "current": 131500.0, "node_id": "node_complex_mcmc", "timestamp": "2026-10-25T14:35:07Z"}
     ```
     Observed circuit breaker event triggered when token threshold is reached.
   - `codex_error_sample.ndjson` (lines 3–11):
     Tool `fsl_flirt` fails at line 4 (duration 320ms), line 7 (duration 315ms), and line 10 (duration 310ms). Line 11 triggers:
     ```json
     {"event": "circuit_breaker", "type": "circuit_breaker", "breaker_reason": "Consecutive failure limit reached for tool fsl_flirt", "metric": "consecutive_failures", "limit": 3.0, "current": 3.0, "node_id": "node_flirt_retry", "timestamp": "2026-10-25T14:45:10Z"}
     ```
     Observed exactly 3 consecutive identical tool failures triggering circuit breaker.

4. **Universal Python Standards Validator (`tests/unit/test_standards_compliance.py`)**:
   - Enforces max line length <= 88 characters.
   - Enforces PascalCase for classes, snake_case for functions.
   - Enforces mandatory type annotations on every argument, kwarg, and return.
   - Enforces custom docstrings with `Parameters` and `Returns` blocks (with `------------` underlines).
   - Enforces zero module-level global variables (`check_zero_globals`, lines 266–343).
   - Enforces single return variable / typed container (`check_single_return`, lines 344–377).

---

## 2. Logic Chain

1. **Class Architecture Derivation**:
   - `TelemetryTap` must intercept streaming text/JSON chunks, parse reasoning traces, track resource usage, and enforce circuit breaker guardrails.
   - To satisfy the zero module-level globals rule, all constants and defaults (`DEFAULT_MAX_NODE_TOKENS = 64000`, `DEFAULT_MAX_WORKFLOW_COST_USD = 10.0`, `DEFAULT_MAX_CONSECUTIVE_TOOL_FAILURES = 3`, `OPEN_THINKING_TAG = "<thinking>"`, `CLOSE_THINKING_TAG = "</thinking>"`) must be encapsulated within a class `TelemetryConstants`.
   - The circuit breaker exception must inherit from `Exception`, take `(reason: str, node_id: str, metric: str = "unknown", limit: float = 0.0, current: float = 0.0)`, and store these attributes for diagnostic inspection.

2. **`<thinking>` Streaming Split-Tag State Machine**:
   - LLM streaming chunks cut arbitrary character boundaries (e.g., `<think` in Chunk 1, `ing>` in Chunk 2; or `<th` in Chunk 1, `ink` in Chunk 2, `ing>` in Chunk 3).
   - A 4-state state machine (`OUTSIDE_TAG`, `MATCHING_OPEN_TAG`, `INSIDE_TAG`, `MATCHING_CLOSE_TAG`) handles arbitrary splits:
     * When encountering `<` outside thinking, buffer candidates matching prefixes of `<thinking>`.
     * If the buffer completes `<thinking>`, transition to `INSIDE_TAG` and discard the tag characters.
     * If candidate characters diverge from the tag prefix (e.g. `<table` or `<`), flush the non-matching buffer to clean text delta and re-evaluate the remainder.
     * When encountering `<` inside thinking, buffer candidates matching prefixes of `</thinking>`.
     * If the buffer completes `</thinking>`, transition to `OUTSIDE_TAG` and discard the tag characters.
     * If candidate characters diverge from `</thinking>` (e.g. `<b` or `<anat>`), flush the non-matching buffer to thinking delta and remain in `INSIDE_TAG`.
     * `flush()` emits any remaining buffered characters upon stream completion.

3. **Circuit Breaker Policies & Consecutive Failure Streak Logic**:
   - **Token Breaker**: Checks if `current_tokens >= max_node_tokens`. If true, raises `CircuitBreakerTripped`.
   - **Cost Breaker**: Checks if `current_cost >= max_workflow_cost_usd`. If true, raises `CircuitBreakerTripped`.
   - **Consecutive Tool Failure Breaker**:
     * Tracks `_last_failed_tool: str | None` and `_consecutive_tool_failures: int`.
     * If `record_tool_call(tool_name, success=False)` is called:
       - If `tool_name == _last_failed_tool`: increment `_consecutive_tool_failures += 1`.
       - If `tool_name != _last_failed_tool`: set `_last_failed_tool = tool_name` and reset `_consecutive_tool_failures = 1`.
       - If `_consecutive_tool_failures >= max_consecutive_tool_failures` (threshold 3): trip breaker!
     * If `record_tool_call(tool_name, success=True)` is called:
       - If `tool_name == _last_failed_tool`: reset `_consecutive_tool_failures = 0` and `_last_failed_tool = None`.
     * This logic guarantees that alternating failures (Tool A fails, Tool B fails, Tool A fails) each have count 1 and never trip, whereas 3 sequential failures of Tool A trip immediately.

4. **Blackboard State Escalation Integration**:
   - When initialized with an optional `blackboard: Blackboard`, tripping any circuit breaker performs two persistent actions:
     1. Transitions the task node to `TaskState.WAITING_OPERATOR` via `blackboard.update_node_state(node_id, TaskState.WAITING_OPERATOR, diagnostic_feedback=reason)`.
     2. Logs a canonical `TelemetryEvent(event_type="circuit_breaker", breaker_reason=reason, ...)` into the Blackboard database via `blackboard.record_telemetry_event(event)`.

5. **Unit Test Suite Partitioning (`tests/unit/test_telemetry.py`)**:
   - Structuring tests into 7 distinct suites (40 test cases total) achieves 100% boundary value, category partition, and adversarial coverage across all requirements.

---

## 3. Caveats

- **Harness Subprocess Process Termination**: `TelemetryTap` detects violations and raises `CircuitBreakerTripped`. Physical termination of OS subprocesses (`SIGTERM`/`SIGKILL`) is the responsibility of `BaseHarnessAdapter` / `DAGOrchestrator` (Milestones 4 and 5), which wrap tap execution in `try ... except CircuitBreakerTripped`.
- **Pre-existing vs Incremental Tokens**: Depending on harness, token usage updates may be reported as cumulative or incremental per chunk. `TelemetryTap` supports both explicit setting via `check_breakers(node_id, current_tokens, current_cost)` and accumulator helpers (`update_token_usage(..., is_cumulative=...)`).

---

## 4. Conclusion & Design Specification

### 4.1 Telemetry Architecture (`src/neuri/core/telemetry.py`)

```python
"""Unified TelemetryTap and Circuit Breaker Subsystem.

Provides real-time stream normalization, chunk-boundary-resilient <thinking>
tag parsing, token and cost accumulation, and circuit breaker guardrails
for the Neuri meta-harness.
"""

from collections.abc import Generator
from datetime import datetime, timezone
from enum import Enum
import json
from typing import Any, Literal
import uuid

from neuri.core.schemas import TaskState, TelemetryEvent


class TelemetryConstants:
    """Encapsulates telemetry configuration constants and defaults.

    Parameters
    ------------
    None

    Returns
    --------
        TelemetryConstants: TelemetryConstants instance
            Constants container.
    """

    DEFAULT_MAX_NODE_TOKENS: int = 64000
    DEFAULT_MAX_WORKFLOW_COST_USD: float = 10.0
    DEFAULT_MAX_CONSECUTIVE_TOOL_FAILURES: int = 3
    DEFAULT_HARNESS_ID: str = "unknown"
    OPEN_THINKING_TAG: str = "<thinking>"
    CLOSE_THINKING_TAG: str = "</thinking>"


class ThinkingParserState(str, Enum):
    """Internal states for the streaming thinking tag parser.

    Parameters
    ------------
    None

    Returns
    --------
        ThinkingParserState: ThinkingParserState enum member
            Parser state machine identifier.
    """

    OUTSIDE_TAG = "OUTSIDE_TAG"
    MATCHING_OPEN_TAG = "MATCHING_OPEN_TAG"
    INSIDE_TAG = "INSIDE_TAG"
    MATCHING_CLOSE_TAG = "MATCHING_CLOSE_TAG"


class CircuitBreakerTripped(Exception):
    """Exception raised when a resource ceiling or fault threshold is exceeded.

    Parameters
    ------------
    reason: str
        Human-readable reason for the circuit breaker trip.
    node_id: str
        Identifier of the DAG task node executing when breaker tripped.
    metric: str
        Metric category causing trip ('tokens', 'cost', or 'tool_consecutive_failures').
        Defaults to 'unknown'.
    limit: float
        Configured budget threshold or maximum allowed failures. Defaults to 0.0.
    current: float
        Observed value that exceeded or met the trip threshold. Defaults to 0.0.

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
    ) -> None:
        super().__init__(reason)
        self.reason: str = reason
        self.node_id: str = node_id
        self.metric: str = metric
        self.limit: float = limit
        self.current: float = current


class ThinkingParser:
    """Streaming parser extracting <thinking> tags across arbitrary chunk boundaries.

    Parameters
    ------------
    None

    Returns
    --------
        ThinkingParser: ThinkingParser instance
            Constructed thinking stream parser.
    """

    def __init__(self) -> None:
        self._state: ThinkingParserState = ThinkingParserState.OUTSIDE_TAG
        self._tag_buffer: str = ""
        self._accumulated_thinking: list[str] = []
        self._accumulated_clean: list[str] = []

    def feed(self, chunk: str) -> tuple[str, str]:
        """Feed a text chunk into parser and extract thinking and clean deltas.

        Parameters
        ------------
        chunk: str
            Raw text stream chunk.

        Returns
        --------
            tuple[str, str]: tuple of (thinking_delta, clean_delta)
                Pair of extracted thinking text delta and clean content delta.
        """
        thinking_out: list[str] = []
        clean_out: list[str] = []

        for ch in chunk:
            if self._state == ThinkingParserState.OUTSIDE_TAG:
                if ch == "<":
                    self._state = ThinkingParserState.MATCHING_OPEN_TAG
                    self._tag_buffer = "<"
                else:
                    clean_out.append(ch)

            elif self._state == ThinkingParserState.MATCHING_OPEN_TAG:
                candidate: str = self._tag_buffer + ch
                if candidate == TelemetryConstants.OPEN_THINKING_TAG:
                    self._state = ThinkingParserState.INSIDE_TAG
                    self._tag_buffer = ""
                elif TelemetryConstants.OPEN_THINKING_TAG.startswith(candidate):
                    self._tag_buffer = candidate
                else:
                    # Diverged from open tag: flush buffer to clean
                    clean_out.append(self._tag_buffer[0])
                    remainder: str = self._tag_buffer[1:] + ch
                    self._tag_buffer = ""
                    self._state = ThinkingParserState.OUTSIDE_TAG
                    for rem_ch in remainder:
                        if self._state == ThinkingParserState.OUTSIDE_TAG:
                            if rem_ch == "<":
                                self._state = ThinkingParserState.MATCHING_OPEN_TAG
                                self._tag_buffer = "<"
                            else:
                                clean_out.append(rem_ch)
                        elif self._state == ThinkingParserState.MATCHING_OPEN_TAG:
                            cand2: str = self._tag_buffer + rem_ch
                            if cand2 == TelemetryConstants.OPEN_THINKING_TAG:
                                self._state = ThinkingParserState.INSIDE_TAG
                                self._tag_buffer = ""
                            elif TelemetryConstants.OPEN_THINKING_TAG.startswith(cand2):
                                self._tag_buffer = cand2
                            else:
                                clean_out.append(self._tag_buffer)
                                clean_out.append(rem_ch)
                                self._tag_buffer = ""
                                self._state = ThinkingParserState.OUTSIDE_TAG

            elif self._state == ThinkingParserState.INSIDE_TAG:
                if ch == "<":
                    self._state = ThinkingParserState.MATCHING_CLOSE_TAG
                    self._tag_buffer = "<"
                else:
                    thinking_out.append(ch)

            elif self._state == ThinkingParserState.MATCHING_CLOSE_TAG:
                candidate = self._tag_buffer + ch
                if candidate == TelemetryConstants.CLOSE_THINKING_TAG:
                    self._state = ThinkingParserState.OUTSIDE_TAG
                    self._tag_buffer = ""
                elif TelemetryConstants.CLOSE_THINKING_TAG.startswith(candidate):
                    self._tag_buffer = candidate
                else:
                    # Diverged from close tag: flush buffer to thinking
                    thinking_out.append(self._tag_buffer[0])
                    remainder = self._tag_buffer[1:] + ch
                    self._tag_buffer = ""
                    self._state = ThinkingParserState.INSIDE_TAG
                    for rem_ch in remainder:
                        if self._state == ThinkingParserState.INSIDE_TAG:
                            if rem_ch == "<":
                                self._state = ThinkingParserState.MATCHING_CLOSE_TAG
                                self._tag_buffer = "<"
                            else:
                                thinking_out.append(rem_ch)
                        elif self._state == ThinkingParserState.MATCHING_CLOSE_TAG:
                            cand2 = self._tag_buffer + rem_ch
                            if cand2 == TelemetryConstants.CLOSE_THINKING_TAG:
                                self._state = ThinkingParserState.OUTSIDE_TAG
                                self._tag_buffer = ""
                            elif TelemetryConstants.CLOSE_THINKING_TAG.startswith(cand2):
                                self._tag_buffer = cand2
                            else:
                                thinking_out.append(self._tag_buffer)
                                thinking_out.append(rem_ch)
                                self._tag_buffer = ""
                                self._state = ThinkingParserState.INSIDE_TAG

        thinking_str: str = "".join(thinking_out)
        clean_str: str = "".join(clean_out)
        if thinking_str:
            self._accumulated_thinking.append(thinking_str)
        if clean_str:
            self._accumulated_clean.append(clean_str)
        res_tuple: tuple[str, str] = (thinking_str, clean_str)
        return res_tuple

    def flush(self) -> tuple[str, str]:
        """Flush any pending buffered tag characters at stream end.

        Parameters
        ------------
        None

        Returns
        --------
            tuple[str, str]: tuple of (thinking_delta, clean_delta)
                Residual flushed thinking and clean strings.
        """
        thinking_res: str = ""
        clean_res: str = ""
        if self._tag_buffer:
            if self._state == ThinkingParserState.MATCHING_OPEN_TAG:
                clean_res = self._tag_buffer
                self._accumulated_clean.append(clean_res)
            elif self._state == ThinkingParserState.MATCHING_CLOSE_TAG:
                thinking_res = self._tag_buffer
                self._accumulated_thinking.append(thinking_res)
            self._tag_buffer = ""
        res: tuple[str, str] = (thinking_res, clean_res)
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
        result_str: str = "".join(self._accumulated_thinking)
        return result_str

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
        result_str: str = "".join(self._accumulated_clean)
        return result_str

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
            self._state == ThinkingParserState.OUTSIDE_TAG
            and not self._tag_buffer
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
                Clears buffers.
        """
        self._state = ThinkingParserState.OUTSIDE_TAG
        self._tag_buffer = ""
        self._accumulated_thinking.clear()
        self._accumulated_clean.clear()


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
        self.workflow_id: str = workflow_id
        self.node_id: str = node_id
        self.harness_id: str = harness_id
        self.max_node_tokens: int = max_node_tokens
        self.max_workflow_cost_usd: float = max_workflow_cost_usd
        self.max_consecutive_tool_failures: int = (
            max_consecutive_tool_failures
        )
        self._blackboard: Any | None = blackboard

        self._thinking_parser: ThinkingParser = ThinkingParser()
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
        stripped: str = chunk.strip()

        # Handle potential NDJSON lines
        lines: list[str] = [ln for ln in chunk.split("\n") if ln.strip()]
        is_ndjson: bool = False
        if lines and all(
            ln.strip().startswith("{") and ln.strip().endswith("}")
            for ln in lines
        ):
            is_ndjson = True

        if is_ndjson:
            for line in lines:
                try:
                    record: dict[str, Any] = json.loads(line)
                    ev: TelemetryEvent | None = self._process_ndjson_record(record)
                    if ev is not None:
                        emitted_events.append(ev)
                except json.JSONDecodeError:
                    self._process_text_chunk(line, emitted_events)
        else:
            self._process_text_chunk(chunk, emitted_events)

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
        thinking_delta, _ = self._thinking_parser.feed(text)
        if thinking_delta:
            event: TelemetryEvent = TelemetryEvent(
                event_id=f"evt-{uuid.uuid4().hex[:12]}",
                workflow_id=self.workflow_id,
                node_id=self.node_id,
                harness_id=self.harness_id,
                event_type="thinking_delta",
                thinking_text=thinking_delta,
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

        if event_name in ("chunk", "response.text.delta"):
            content: str = str(record.get("content", ""))
            thinking_delta, _ = self._thinking_parser.feed(content)
            if thinking_delta:
                result_event = TelemetryEvent(
                    event_id=f"evt-{uuid.uuid4().hex[:12]}",
                    workflow_id=self.workflow_id,
                    node_id=self.node_id,
                    harness_id=self.harness_id,
                    event_type="thinking_delta",
                    thinking_text=thinking_delta,
                )
                self._log_event(result_event)

        elif event_name in ("token_usage", "usage", "response.token_usage"):
            in_tok: int = int(record.get("input_tokens", 0))
            out_tok: int = int(record.get("output_tokens", 0))
            cached_tok: int = int(record.get("cached_tokens", 0))
            reasoning_tok: int = int(record.get("reasoning_tokens", 0))
            cost: float = float(record.get("cost_usd", 0.0))
            self.update_token_usage(
                input_tokens=in_tok,
                output_tokens=out_tok,
                cached_tokens=cached_tok,
                reasoning_tokens=reasoning_tok,
                cost_usd=cost,
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
                estimated_cost_usd=cost,
            )
            self._log_event(result_event)

        elif event_name in (
            "tool_lifecycle", "tool_call", "tool.call.started",
            "tool.call.completed", "tool.call.failed"
        ):
            tool_name: str = str(record.get("tool_name", "unknown"))
            tool_host: str = str(record.get("tool_host", "localhost"))
            status: str = str(
                record.get("tool_status") or record.get("status") or "completed"
            )
            duration_ms: int | None = (
                int(record["duration_ms"]) if "duration_ms" in record else None
            )
            if "failed" in event_name or status == "failed":
                norm_status: Literal["started", "completed", "failed"] = "failed"
                self.record_tool_call(
                    tool_name, success=False, error_message=record.get("error")
                )
            elif "started" in event_name or status == "started":
                norm_status = "started"
            else:
                norm_status = "completed"
                self.record_tool_call(tool_name, success=True)

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
            reason: str = str(record.get("breaker_reason", "Circuit breaker tripped"))
            self._breaker_tripped = True
            self._breaker_reason = reason
            result_event = TelemetryEvent(
                event_id=f"evt-{uuid.uuid4().hex[:12]}",
                workflow_id=self.workflow_id,
                node_id=self.node_id,
                harness_id=self.harness_id,
                event_type="circuit_breaker",
                breaker_reason=reason,
            )
            self._log_event(result_event)

        return result_event

    def record_tool_call(
        self,
        tool_name: str,
        success: bool,
        error_message: str | None = None,
    ) -> None:
        """Record outcome of a tool execution and enforce consecutive failure limit.

        Parameters
        ------------
        tool_name: str
            Name of the executed tool.
        success: bool
            Whether execution succeeded.
        error_message: str | None
            Error diagnostic details if failed. Defaults to None.

        Returns
        --------
            None: NoneType object
                Updates tool failure counters and raises if ceiling met.
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
                self._trigger_breaker(
                    reason=reason,
                    metric="tool_consecutive_failures",
                    limit=float(self.max_consecutive_tool_failures),
                    current=float(self._consecutive_tool_failures),
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
            )

    def update_token_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
        reasoning_tokens: int = 0,
        cost_usd: float = 0.0,
    ) -> None:
        """Update accumulated token metrics and check circuit breakers.

        Parameters
        ------------
        input_tokens: int
            Cumulative or incremental input tokens.
        output_tokens: int
            Cumulative or incremental output tokens.
        cached_tokens: int
            Prompt cached tokens. Defaults to 0.
        reasoning_tokens: int
            Thinking tokens. Defaults to 0.
        cost_usd: float
            Cumulative cost in USD. Defaults to 0.0.

        Returns
        --------
            None: NoneType object
                Updates state and evaluates breakers.
        """
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        self._cached_tokens = cached_tokens
        self._reasoning_tokens = reasoning_tokens
        self._cost_usd = cost_usd

        total: int = self._input_tokens + self._output_tokens
        self.check_breakers(self.node_id, total, self._cost_usd)

    def _trigger_breaker(
        self,
        reason: str,
        metric: str,
        limit: float,
        current: float,
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

        Returns
        --------
            None: NoneType object
                Never returns normally; raises CircuitBreakerTripped.
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
                Metrics dictionary containing token, cost, tool, and breaker tallies.
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
        thinking_res, _ = self._thinking_parser.flush()
        if thinking_res:
            event: TelemetryEvent = TelemetryEvent(
                event_id=f"evt-{uuid.uuid4().hex[:12]}",
                workflow_id=self.workflow_id,
                node_id=self.node_id,
                harness_id=self.harness_id,
                event_type="thinking_delta",
                thinking_text=thinking_res,
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
```

---

### 4.2 Comprehensive Unit Test Suite Architecture (`tests/unit/test_telemetry.py`)

The test file `tests/unit/test_telemetry.py` is organized into 7 explicit suites with 40 test functions:

#### Suite 1: `<thinking>` Parser Tests (10 tests)
1. `test_thinking_parser_normal`: Simple `<thinking>thought</thinking>` extraction and clean text separation.
2. `test_thinking_parser_multiline`: Multi-line reasoning traces across 5 lines.
3. `test_thinking_parser_split_open_tag_2_chunks`: Opening tag split as `"<think"` and `"ing>validating scan</thinking>"`.
4. `test_thinking_parser_split_close_tag_2_chunks`: Closing tag split as `"<thinking>validating scan</think"` and `"ing>all good"`.
5. `test_thinking_parser_split_open_tag_3_chunks`: Opening tag split as `"<th"`, `"ink"`, `"ing>reasoning</thinking>"`.
6. `test_thinking_parser_split_close_tag_3_chunks`: Closing tag split as `"<thinking>reasoning</th"`, `"ink"`, `"ing>done"`.
7. `test_thinking_parser_unclosed_tag`: Stream terminates with unclosed `<thinking>in progress`; asserts `is_thinking_closed() == False`, thinking text extracted, no crash.
8. `test_thinking_parser_empty_thinking`: `<thinking></thinking>` and `<thinking>   </thinking>` handled cleanly without error.
9. `test_thinking_parser_nested_brackets_and_pseudo_tags`: `<thinking>inspecting <T1w> and <bold> files</thinking>` preserves nested pseudo-tags inside thinking text.
10. `test_thinking_parser_multiple_thinking_blocks`: Multiple sequential `<thinking>...</thinking>` blocks interleaved with clean text.

#### Suite 2: Token and Cost Accumulators (5 tests)
11. `test_accumulator_initial_state`: All counters 0, cost 0.0, breaker not tripped.
12. `test_accumulator_incremental_updates`: Incremental input and output token updates correctly summed in `get_accumulated_tokens()`.
13. `test_accumulator_cached_and_reasoning_tokens`: Cached and reasoning token tallies preserved and returned in `get_metrics()`.
14. `test_accumulator_cost_tracking`: Floating point cost accumulation verified with `pytest.approx()`.
15. `test_accumulator_reset`: Calling `reset()` clears all counters and returns accumulators to zero.

#### Suite 3: `max_node_tokens` Circuit Breaker Trip (5 tests)
16. `test_token_breaker_trip_at_exact_limit`: Setting `max_node_tokens=50000`, updating tokens to exactly 50000 trips `CircuitBreakerTripped`.
17. `test_token_breaker_trip_above_limit`: Setting `max_node_tokens=50000`, updating tokens to 50001 trips `CircuitBreakerTripped`.
18. `test_token_breaker_non_trip_below_limit`: Updating tokens to 49999 does not trip.
19. `test_token_breaker_exception_attributes`: Asserts `exc.node_id == "node-01"`, `exc.metric == "tokens"`, `exc.limit == 50000.0`, `exc.current == 55000.0`.
20. `test_token_breaker_via_process_chunk_usage`: Processing NDJSON `token_usage` record exceeding limit raises `CircuitBreakerTripped`.

#### Suite 4: `max_workflow_cost_usd` Circuit Breaker Trip (5 tests)
21. `test_cost_breaker_trip_at_exact_limit`: Setting `max_workflow_cost_usd=2.50`, updating cost to 2.50 trips `CircuitBreakerTripped`.
22. `test_cost_breaker_trip_above_limit`: Updating cost to 2.51 trips `CircuitBreakerTripped`.
23. `test_cost_breaker_non_trip_below_limit`: Updating cost to 2.49 does not trip.
24. `test_cost_breaker_exception_attributes`: Asserts `exc.metric == "cost"`, `exc.limit == 2.50`, `exc.current == 3.00`.
25. `test_cost_breaker_via_process_chunk_usage`: Processing NDJSON usage record exceeding cost raises `CircuitBreakerTripped`.

#### Suite 5: Consecutive Identical Tool Failure Breaker (6 tests)
26. `test_consecutive_3_identical_tool_failures_trip`: Tool `fsl_bet` fails 3 times sequentially -> trips `CircuitBreakerTripped`.
27. `test_consecutive_failure_exception_attributes`: Asserts `exc.metric == "tool_consecutive_failures"`, `exc.limit == 3.0`, `exc.current == 3.0`.
28. `test_alternating_tool_failures_non_trip`: Tool A fails, Tool B fails, Tool A fails, Tool B fails -> 0 breaker trips, each streak resets to 1.
29. `test_tool_success_resets_streak`: Tool A fails twice, succeeds once, then fails once -> total count is 1, no breaker trip.
30. `test_different_tool_success_behavior`: Tool A fails, Tool B succeeds, Tool A fails -> streak broken, no breaker trip.
31. `test_tool_failure_via_process_chunk_ndjson`: Processing 3 NDJSON `tool_lifecycle` records with status `"failed"` triggers breaker.

#### Suite 6: Blackboard State Escalation Integration (5 tests)
32. `test_blackboard_escalation_on_token_breaker_trip`: Tap initialized with real SQLite WAL Blackboard; node in `RUNNING` state; token breaker trips -> verifies node state in Blackboard transitioned to `WAITING_OPERATOR`.
33. `test_blackboard_escalation_on_cost_breaker_trip`: Cost breaker trips -> verifies node state in Blackboard transitioned to `WAITING_OPERATOR` and diagnostic feedback recorded.
34. `test_blackboard_escalation_on_tool_failure_breaker_trip`: Consecutive tool failures trip -> verifies node state in Blackboard transitioned to `WAITING_OPERATOR`.
35. `test_blackboard_telemetry_event_persistence`: All processed events (thinking_delta, token_usage, tool_lifecycle, circuit_breaker) persisted in SQLite and retrievable via `blackboard.list_telemetry_events()`.
36. `test_blackboard_diagnostic_feedback_content`: Task node's `diagnostic_feedback` list contains the exact breaker reason string.

#### Suite 7: Deterministic NDJSON Stream Fixture Replay (4 tests)
37. `test_replay_agy_stream_sample`: Replays `tests/fixtures/agy_stream_sample.ndjson`; asserts thinking tag extraction across split chunks, token count 3600, cost 0.032, zero breaker trips.
38. `test_replay_agy_breaker_sample`: Replays `tests/fixtures/agy_breaker_sample.ndjson`; asserts `CircuitBreakerTripped` raised on token limit 64000.
39. `test_replay_codex_stream_sample`: Replays `tests/fixtures/codex_stream_sample.ndjson`; asserts tool lifecycle events, ANTs SyN duration 8450ms, clean completion.
40. `test_replay_codex_error_sample`: Replays `tests/fixtures/codex_error_sample.ndjson`; asserts 3 consecutive `fsl_flirt` failures trip circuit breaker.

---

### 4.3 Universal Python Standards Compliance Verification Plan

1. **AST Compliance Checker Execution**:
   - Running `pytest -v tests/unit/test_standards_compliance.py` directly validates all files in `src/neuri/` against:
     * Line length limit: `<= 88` characters.
     * Naming: `PascalCase` classes (`TelemetryTap`, `ThinkingParser`, `CircuitBreakerTripped`, `TelemetryConstants`, `ThinkingParserState`), `snake_case` functions/methods.
     * Docstrings: Mandatory `Parameters` and `Returns` blocks with `------------` underlines on every class and method.
     * Zero globals: No module-level constants or variables; everything inside `TelemetryConstants`.
     * Single returns: Every function assigns its return value to a typed variable before returning.
2. **Pytest Test Execution**:
   - Run `uv run pytest -v tests/unit/test_telemetry.py` to ensure all 40 tests execute in <2 seconds with 0 warnings and 0 failures.

---

## 5. Verification Method

### 5.1 Verification Commands
Once implemented by the worker agent:
```bash
# 1. Run unit test suite in isolation
uv run pytest -v tests/unit/test_telemetry.py

# 2. Run AST standards compliance validator
uv run pytest -v tests/unit/test_standards_compliance.py

# 3. Run full test suite across M1, M2, and M3
uv run pytest -v
```

### 5.2 Files to Inspect
- `src/neuri/core/telemetry.py`: Must contain `TelemetryTap`, `ThinkingParser`, `CircuitBreakerTripped`, `TelemetryConstants`, `ThinkingParserState`.
- `tests/unit/test_telemetry.py`: Must contain all 40 test functions across the 7 specified suites.

### 5.3 Invalidation Conditions
- Any line exceeding 88 characters in `src/neuri/core/telemetry.py` or `tests/unit/test_telemetry.py`.
- Any module-level global variable (e.g. `DEFAULT_MAX_TOKENS = 64000` outside a class).
- Any function missing a type annotation or docstring with `Parameters` / `Returns` sections.
- Failure of split-tag parsing on arbitrary multi-chunk boundaries (e.g. `<think` + `ing>`).
- Alternating tool failures incorrectly tripping the consecutive failure breaker.
- Failure to transition Blackboard node state to `TaskState.WAITING_OPERATOR` on breaker trip.
