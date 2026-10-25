# BRIEFING — 2026-10-25T20:05:40Z

## Mission
Investigate and design token/cost tracking and circuit breaker policies in `src/neuri/core/telemetry.py` conforming to Universal Python Standards.

## 🔒 My Identity
- Archetype: Explorer
- Roles: Investigator, Synthesizer
- Working directory: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m3_2
- Original parent: 93d2f271-2e53-4e5d-a816-275a3ea34195
- Milestone: M3-2 Circuit Breakers & Pricing

## 🔒 Key Constraints
- Read-only investigation — do NOT implement directly in src/
- 100% compliance with Universal Python Standards (`/Users/mszdjh3/.gemini/config/rules/python_standard.md`): PEP 8, strict typing, docstrings, no globals, single return
- Circuit breaker policies: max_node_tokens (64k), max_workflow_cost_usd ($10.00), 3 consecutive identical tool call failures
- Exception hierarchy: `CircuitBreakerTripped(NeuriException)` with reason and node_id
- Blackboard integration contract: transition to `TaskState.WAITING_OPERATOR` and append diagnostic error feedback

## Current Parent
- Conversation ID: 93d2f271-2e53-4e5d-a816-275a3ea34195
- Updated: 2026-10-25T20:05:40Z

## Investigation State
- **Explored paths**:
  - `ORIGINAL_REQUEST.md`, `PROJECT.md`, `technical_documenation/`
  - `src/neuri/core/schemas.py` (`TaskState`, `TelemetryEvent`, `NeuriTaskEnvelope`)
  - `src/neuri/core/blackboard.py` (`VALID_TRANSITIONS`, `update_node_state`, `record_telemetry_event`)
  - `src/neuri/core/config.py` (`BudgetConfig`, `HarnessRoutingConfig`)
  - `tests/fixtures/` (`agy_breaker_sample.ndjson`, `codex_error_sample.ndjson`, etc.)
  - `tests/unit/test_standards_compliance.py` (AST checks)
- **Key findings**:
  - Root `NeuriException(Exception)` and `CircuitBreakerTripped` hierarchy designed with metric contexts.
  - Model pricing encapsulated in `ModelPricingTable` without module-level globals ($3.00/1M input, $15.00/1M output, configurable).
  - `TokenCostTracker` supports incremental vs cumulative chunk updates and tracks both node and workflow tallies.
  - 3 Breakers (`max_node_tokens` 64k, `max_workflow_cost_usd` $10, 3 consecutive identical tool failures with alternating safety) fully formulated.
  - Blackboard integration contract: transitions node to `TaskState.WAITING_OPERATOR`, appends diagnostic error feedback to `task_nodes`, logs `TelemetryEvent` to `telemetry_events` table, and sets workflow status.
- **Unexplored areas**: None within M3-2 scope.

## Key Decisions Made
- Encapsulated pricing tables in `ModelPricingTable` class to satisfy AST validator's zero module-level globals rule.
- Provided subclasses `NodeTokenLimitExceeded`, `WorkflowCostLimitExceeded`, and `ConsecutiveToolFailureLimitExceeded` under `CircuitBreakerTripped`.
- Generated drop-in reference implementation in `proposed_circuit_breakers.py` with 100% standards compliance (line lengths <= 88, docstrings, types).

## Artifact Index
- DISPATCH.md — Received orchestrator mission instructions
- BRIEFING.md — Working memory and status
- progress.md — Liveness heartbeat and step tracking
- proposed_circuit_breakers.py — Complete drop-in implementation code
- handoff.md — 5-component handoff report
