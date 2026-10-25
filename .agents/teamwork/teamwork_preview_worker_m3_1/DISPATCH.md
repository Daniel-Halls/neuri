## 2026-10-25T20:06:48Z

You are worker_m3_1, a teamwork_preview_worker implementing Milestone 3 of Neuri (Unified TelemetryTap & Circuit Breakers).

## Working Directory
`/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_worker_m3_1/`

## Exclusive Write Ownership
You have exclusive write ownership over:
- `/Users/mszdjh3/code/neuri/src/neuri/core/telemetry.py`
- `/Users/mszdjh3/code/neuri/src/neuri/core/__init__.py`
- `/Users/mszdjh3/code/neuri/tests/unit/test_telemetry.py`
Do NOT modify files owned by other modules.

## Context Files to Read First
1. `/Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md` (Verbatim user specification)
2. `/Users/mszdjh3/code/neuri/PROJECT.md` (Architecture, contracts, Milestone 3 scope)
3. `/Users/mszdjh3/code/neuri/TEST_INFRA.md` (Test strategies, replay fixtures)
4. `/Users/mszdjh3/.gemini/config/rules/python_standard.md` (Universal Python Standards)
5. Explorer Handoffs and Design Artifacts:
   - `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m3_1/handoff.md` (`StreamingThinkingParser`, `StreamEventNormalizer`, sliding-suffix matching for split `<thinking>` tags)
   - `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m3_2/handoff.md` and `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m3_2/proposed_circuit_breakers.py` (`NeuriException`, `CircuitBreakerTripped` and subclasses `NodeTokenLimitExceeded`, `WorkflowCostLimitExceeded`, `ConsecutiveToolFailureLimitExceeded`, `ModelPricing`, `ModelPricingTable`, `TokenCostTracker`, `CircuitBreakerPolicy`, `BlackboardBreakerCoordinator`)
   - `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m3_3/handoff.md` (`TelemetryConstants`, `TelemetryTap` integration, 40-test suite across 7 categories)

## MANDATORY INTEGRITY WARNING
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Universal Python Standards (NON-NEGOTIABLE)
All code written in `src/neuri/` and `tests/` MUST strictly comply with `/Users/mszdjh3/.gemini/config/rules/python_standard.md`:
- Max line length strictly <= 88 characters.
- PascalCase for classes, snake_case for functions and variables.
- Type annotations on all function/method arguments and return values.
- Docstrings on EVERY class, function, and method with `Parameters\n  ------------` and `Returns\n  --------` blocks.
- ZERO module-level global variables. Encapsulate all configuration, pricing, and constants inside classes (`TelemetryConstants`, `ModelPricingTable`, etc.).
- Single return variable per function (assign to a typed variable before returning).
- Validated via `tests/unit/test_standards_compliance.py`.

## Implementation Requirements for `src/neuri/core/telemetry.py`
Synthesize the 3 explorer designs into a clean, cohesive, fully functional module:
1. `TelemetryConstants`: Class encapsulating all default budget thresholds, tag names, and rate constants (`DEFAULT_MAX_NODE_TOKENS = 64000`, `DEFAULT_MAX_WORKFLOW_COST_USD = 10.0`, `DEFAULT_MAX_CONSECUTIVE_TOOL_FAILURES = 3`, `DEFAULT_HARNESS_ID = "unknown"`, `OPEN_THINKING_TAG = "<thinking>"`, `CLOSE_THINKING_TAG = "</thinking>"`).
2. Exception Hierarchy:
   - `NeuriException(Exception)`
   - `CircuitBreakerTripped(NeuriException)` with attributes `(reason, node_id, metric, limit, current)`
   - `NodeTokenLimitExceeded(CircuitBreakerTripped)`
   - `WorkflowCostLimitExceeded(CircuitBreakerTripped)`
   - `ConsecutiveToolFailureLimitExceeded(CircuitBreakerTripped)` with `tool_name`
3. Pricing & Cost Tracking:
   - `ModelPricing(BaseModel)`: with fields `input_cost_per_million`, `output_cost_per_million`, `cached_cost_per_million`, `reasoning_cost_per_million`.
   - `ModelPricingTable`: Registry providing rates for `agy`, `antigravity`, `codex`, `opencode`, `openclaw`, `ollama`, `ollama_local`, and `default`.
   - `TokenCostTracker`: Tracks prompt, completion, cache, reasoning tokens, and cumulative USD cost per node and workflow.
4. Streaming Thinking Parser:
   - `StreamingThinkingParser`: Robust state machine maintaining sliding-suffix buffers across arbitrary chunk splits (`<think` + `ing>`, `</think` + `ing>`, `<th` + `ink` + `ing>`), false alarms (`<think of a number`), multiple blocks, unclosed blocks, and `flush()`. Returns `ParsedStreamChunk`.
5. Stream Event Normalizer:
   - `StreamEventNormalizer`: Normalizes raw strings and NDJSON records into typed `TelemetryEvent`s (`thinking_delta`, `token_usage`, `tool_lifecycle`, `circuit_breaker`) and clean visible content.
6. Unified `TelemetryTap`:
   - Attributes: `workflow_id`, `node_id`, `harness_id`, budgets, optional `blackboard`.
   - Methods:
     - `process_chunk(chunk: str) -> list[TelemetryEvent]`
     - `record_tool_call(tool_name: str, success: bool, error_message: str | None = None, duration_ms: int | None = None, tool_host: str = "localhost") -> None`
       - Consecutive failure breaker: increments streak when the identical tool fails consecutively. Alternating failures (Tool A fails, Tool B fails) reset streak to 1. Success resets streak to 0. 3 consecutive identical failures trip `ConsecutiveToolFailureLimitExceeded`.
     - `check_breakers(node_id: str, current_tokens: int, current_cost: float) -> None`
     - `update_token_usage(input_tokens: int, output_tokens: int, cached_tokens: int = 0, reasoning_tokens: int = 0, cost_usd: float = 0.0, is_cumulative: bool = False) -> None`
     - `get_metrics() -> dict[str, Any]`
     - `get_thinking_text() -> str`
     - `get_clean_text() -> str`
     - `is_breaker_tripped() -> bool`
     - `get_events() -> list[TelemetryEvent]`
     - `flush() -> list[TelemetryEvent]`
     - `reset() -> None`
   - Blackboard Escalation on Breaker Trip:
     - When any breaker trips, if `blackboard` is present:
       1. Calls `blackboard.update_node_state(node_id, TaskState.WAITING_OPERATOR, diagnostic_feedback=reason)`
       2. Calls `blackboard.record_telemetry_event(event)` with `event_type="circuit_breaker"`
       3. Updates workflow status to `WAITING_OPERATOR`

## Implementation Requirements for `src/neuri/core/__init__.py`
Export all primary telemetry symbols (`TelemetryTap`, `CircuitBreakerTripped`, `NodeTokenLimitExceeded`, `WorkflowCostLimitExceeded`, `ConsecutiveToolFailureLimitExceeded`, `NeuriException`, `TelemetryConstants`, `StreamingThinkingParser`, `ModelPricing`, `ModelPricingTable`, `TokenCostTracker`).

## Test Requirements for `tests/unit/test_telemetry.py`
Implement the 40 test functions across 7 test suites as specified in `explorer_m3_3/handoff.md`:
- Suite 1: `<thinking>` Parser Tests (10 tests)
- Suite 2: Token and Cost Accumulators (5 tests)
- Suite 3: `max_node_tokens` Breaker (5 tests)
- Suite 4: `max_workflow_cost_usd` Breaker (5 tests)
- Suite 5: Consecutive Identical Tool Failure Breaker (6 tests)
- Suite 6: Blackboard Escalation Integration (5 tests)
- Suite 7: NDJSON Fixture Stream Replay (4 tests)
