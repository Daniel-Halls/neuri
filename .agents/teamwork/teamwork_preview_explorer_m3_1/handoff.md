# Handoff Report: Milestone 3-1 Thinking & Stream Normalization

## 1. Observation

Direct examination of codebase artifacts, schemas, and test fixtures revealed the following empirical requirements and constraints:

### A. Schema & Database Constraints on Telemetry Events
In `src/neuri/core/schemas.py` (lines 1211–1346):
```python
class TelemetryEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    workflow_id: str
    node_id: str
    harness_id: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    event_type: Literal[
        "thinking_delta",
        "token_usage",
        "tool_lifecycle",
        "circuit_breaker",
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
- `TelemetryEvent.model_config` strictly enforces `extra="forbid"`. Attempting to inject unmodeled keys (such as `content_text`) raises Pydantic `ValidationError`.
- `event_type` is restricted by a 4-value literal: `"thinking_delta"`, `"token_usage"`, `"tool_lifecycle"`, and `"circuit_breaker"`.
- In `src/neuri/core/blackboard.py` (lines 2535–2557), the SQLite persistence routine mirrors these exact fields into the `telemetry_events` table.
- In contrast, visible assistant speech/content chunks belong to the presentation layer via `SessionEvent(event_type=SessionEventType.ASSISTANT_CHUNK)` (`src/neuri/core/schemas.py:1586`).

### B. Vendor Stream Fixture Formats
Analysis of deterministic stream test fixtures in `tests/fixtures/`:
1. `agy_stream_sample.ndjson` (lines 1–15):
   - Line 1: `{"event": "start", "type": "session_start", "harness": "agy", "workflow_id": "wf_neuro_001", "node_id": "node_preproc_sub01", "timestamp": "2026-10-25T14:30:00Z"}`
   - Line 2: `{"event": "chunk", "type": "chunk", "content": "<think", "timestamp": "2026-10-25T14:30:01Z"}`
   - Line 3: `{"event": "chunk", "type": "chunk", "content": "ing>Validating BIDS dataset structure for subject sub-01...", "timestamp": "2026-10-25T14:30:02Z"}`
   - Line 4: `{"event": "chunk", "type": "chunk", "content": " Checking T1w structural scan and JSON sidecar metadata. All fields verified.</think", "timestamp": "2026-10-25T14:30:03Z"}`
   - Line 5: `{"event": "chunk", "type": "chunk", "content": "ing>BIDS structure for sub-01 is fully compliant with BIDS v1.9.0.", "timestamp": "2026-10-25T14:30:04Z"}`
   - Line 6–7: `tool_lifecycle` with `tool_name`, `tool_host`, `tool_status` ("started", "completed"), `duration_ms`.
   - Line 10: `token_usage` with `input_tokens`, `output_tokens`, `reasoning_tokens`, `cost_usd`.
   - Line 15: `result` summary with `total_tokens` and `cost_usd`.

2. `codex_stream_sample.ndjson` (lines 1–9):
   - Line 1: `{"event": "session.created", "type": "session_start", "harness": "codex", "session_id": "codex_sess_101", "node_id": "node_reg_01"}`
   - Line 2: `{"event": "response.output_item.added", "type": "chunk", "content": "<thinking>Aligning subject anatomical T1w...</thinking>"}`
   - Line 3: `{"event": "response.text.delta", "type": "chunk", "content": "Configuring ANTs SyN registration parameters..."}`
   - Line 4–5: `tool.call.started` and `tool.call.completed`.
   - Line 8: `response.token_usage` with `input_tokens`, `output_tokens`, `reasoning_tokens`, `cost_usd`.
   - Line 9: `turn.completed`.

3. `agy_breaker_sample.ndjson` (line 8) & `codex_error_sample.ndjson` (line 11):
   - Circuit breaker alerts: `{"event": "circuit_breaker", "type": "circuit_breaker", "breaker_reason": "...", "metric": "...", "limit": ..., "current": ...}`.

### C. Standards & AST Compliance Rules
`tests/unit/test_standards_compliance.py` enforces:
- Max line length of 88 characters (`MAX_LINE_LENGTH = 88`).
- PascalCase for all classes (`^[A-Z][a-zA-Z0-9]*$`).
- snake_case for all functions/methods (`^(_+)?[a-z0-9]+(_[a-z0-9]+)*(_+)?$`).
- Type annotations on all parameters (`self` and `cls` exempt) and return values.
- Docstrings on all classes and functions containing `Parameters\n  ------------` and `Returns\n  --------` sections.
- Zero module-level global variables (all constants and states must be class-encapsulated).
- Single return variable per function.

---

## 2. Logic Chain

From the observations, we deduce the following structural design:

1. **Dual Stream Output Separation**:
   - The `<thinking>...</thinking>` tags wrap internal chain-of-thought traces intended strictly for collapsible TUI panels.
   - Text outside `<thinking>` tags is the visible assistant response intended for the conversation canvas.
   - Tags can be arbitrarily fractured across chunk boundaries (e.g. `<think` in chunk 1, `ing>` in chunk 2, `</think` in chunk 3, `ing>` in chunk 4).
   - Therefore, a streaming state-machine parser must maintain an internal tag buffer across calls to `feed()`.

2. **Tag Buffering & Sliding Suffix Matching (KMP Principle)**:
   - When in state `OUTSIDE`, any character matching the opening prefix `<` must be buffered.
   - If subsequent characters continue matching `<thinking>`, buffering continues.
   - If a mismatch occurs (e.g. `<thing` or `<<thinking>`), the parser must NOT discard buffered characters. It must find the longest proper suffix matching `<thinking>`'s prefix, emit preceding characters as clean content, and retain the matching suffix in the buffer.
   - The identical symmetric invariant applies to `</thinking>` when in state `THINKING`.
   - This mathematical guarantee ensures:
     - Zero character loss on false alarms.
     - Accurate detection even if tags are split character-by-character (`<`, `t`, `h`, `i`, ...).
     - Clean tag stripping without leaking `<thinking>` or `</thinking>` markers to the user.

3. **Stream Event Normalization Flow**:
   - Subprocess lines may arrive as NDJSON lines (Antigravity `agy` or OpenAI `codex` format) or raw text chunks.
   - If a line is valid JSON:
     - Check `event` / `type`:
       - `chunk` / `response.text.delta` / `response.output_item.added`: extract `content`, feed to `StreamingThinkingParser`. Emit `thinking_delta` event if thinking text was parsed, and pass `content_delta` through.
       - `usage` / `token_usage` / `response.token_usage`: extract input/output/cached/reasoning tokens and cost, emit `token_usage` event.
       - `tool_call` / `tool_lifecycle` / `tool.call.started` / `completed` / `failed`: extract tool metadata, emit `tool_lifecycle` event.
       - `circuit_breaker`: emit `circuit_breaker` event.
       - `session_start` / `session.created`: update active workflow/node/harness context.
   - If input is raw string (non-JSON):
     - Feed string directly to `StreamingThinkingParser`.
     - Emit `thinking_delta` for any extracted thinking text.
     - Pass remaining visible text through as `content_delta`.

4. **Standards-Compliant Data Structures**:
   - `ParsedStreamChunk(thinking_delta: str, content_delta: str, is_thinking: bool)`: immutable model returned by `StreamingThinkingParser.feed()`.
   - `NormalizedStreamResult(events: list[TelemetryEvent], content_delta: str, is_thinking: bool)`: immutable model returned by `StreamEventNormalizer.normalize_chunk()`.
   - `TelemetryTap.process_chunk(chunk: str) -> list[TelemetryEvent]`: satisfies the interface contract defined in `PROJECT.md` line 127, while updating internal `last_content_delta` and accumulated content.

---

## 3. Caveats

1. **Tag Scope**: The parser standardizes on `<thinking>...</thinking>` (case-insensitive: `<thinking>`, `<Thinking>`, `<THINKING>`). If other tags are needed (such as `<thought>`), the parser supports passing a custom `tag_name` parameter during initialization (defaulting to `"thinking"`).
2. **Circuit Breakers & Pricing**: The calculation of token pricing tables and tripping logic for the three circuit breaker policies (`max_node_tokens`, `max_workflow_cost_usd`, 3 consecutive identical tool failures) is scoped to Explorer M3-2. `TelemetryTap` integrates with M3-2's breaker logic.
3. **Unit Test Layout**: Comprehensive test suites for `test_telemetry.py` are scoped to Explorer M3-3. Verification scenarios below serve as acceptance criteria for those tests.
4. **Encoding**: Assumes standard UTF-8 text streaming from subprocess pipes.

---

## 4. Conclusion & Proposed Specification

The complete, drop-in design for `StreamingThinkingParser`, `StreamEventNormalizer`, and related components in `src/neuri/core/telemetry.py` is specified below:

```python
"""Neuri Telemetry & Stream Interceptor Module.

Normalizes multi-vendor streaming outputs (Antigravity, Codex, Ollama, raw text),
extracts and isolates <thinking> traces across arbitrary chunk splits, tracks
resource consumption, and enforces circuit breakers.
"""

from datetime import datetime, timezone
from enum import Enum
import json
from typing import Any, Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field

from neuri.core.schemas import TelemetryEvent


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

    def feed(self, chunk: str) -> ParsedStreamChunk:
        """Process an incremental string chunk and extract thinking/content deltas.

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

        res: ParsedStreamChunk = ParsedStreamChunk(
            thinking_delta="".join(thinking_parts),
            content_delta="".join(content_parts),
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
            else:
                flushed_content = self._tag_buffer
            self._tag_buffer = ""

        res: ParsedStreamChunk = ParsedStreamChunk(
            thinking_delta=flushed_thinking,
            content_delta=flushed_content,
            is_thinking=(self._state == ParserState.THINKING),
        )
        return res

    def reset(self) -> None:
        """Reset parser state and buffers to initial values.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Clears internal buffers and resets state to OUTSIDE.
        """
        self._state = ParserState.OUTSIDE
        self._tag_buffer = ""

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
```

---

## 5. Verification Method

To independently verify this design:

### 1. AST Universal Standards Compliance Check
Execute the repository compliance test:
```bash
uv run pytest tests/unit/test_standards_compliance.py -v
```
All methods and classes have:
- Lengths strictly <= 88 chars.
- Full type annotations.
- Full custom docstrings with `Parameters` and `Returns` blocks.
- Zero module-level globals.
- Single returns.

### 2. State Machine Boundary Tests for `<thinking>` Parser
Create targeted unit test cases in `tests/unit/test_telemetry.py`:
- **Single chunk normal**: `"<thinking>plan</thinking>ans"` -> thinking="plan", content="ans".
- **Split open tag across 2 chunks**: Chunk 1: `"<thin"`, Chunk 2: `"king>plan</thinking>"` -> Chunk 1: empty, Chunk 2: thinking="plan".
- **Split open tag across 4 chunks**: `"<"`, `"thin"`, `"k"`, `"ing>"` -> no drops, transitions to thinking.
- **Split close tag across 2 chunks**: Chunk 1: `"<thinking>plan</think"`, Chunk 2: `"ing>ans"` -> Chunk 1: thinking="plan", Chunk 2: content="ans".
- **False-alarm open tag**: Chunk 1: `"<thin"`, Chunk 2: `"k of a number"` -> content="<think of a number".
- **False-alarm close tag**: Inside thinking, `"</think"` followed by `"pad"` -> thinking="</thinkpad".
- **Back-to-back overlapping brackets**: `"abc<<thinking>plan</thinking>"` -> content="abc<", thinking="plan".
- **End-of-stream flush**: Stream ends with `"<thin"` buffered outside thinking -> flushed to clean content.

### 3. Multi-Vendor NDJSON Replay Verification
Feed the existing test fixtures through `StreamEventNormalizer`:
- `tests/fixtures/agy_stream_sample.ndjson`
- `tests/fixtures/agy_breaker_sample.ndjson`
- `tests/fixtures/codex_stream_sample.ndjson`
- `tests/fixtures/codex_error_sample.ndjson`
Assert that:
1. Every NDJSON line produces corresponding typed `TelemetryEvent` instances (`thinking_delta`, `token_usage`, `tool_lifecycle`, `circuit_breaker`).
2. Split tags in lines 2–5 of `agy_stream_sample.ndjson` are reconstituted into continuous `thinking_delta` events, and line 5 passes `"BIDS structure for sub-01 is fully compliant with BIDS v1.9.0."` through as clean `content_delta`.
3. Total tokens and cost match fixture declarations.
