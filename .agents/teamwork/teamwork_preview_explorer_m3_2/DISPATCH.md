## 2026-10-25T19:57:34Z
Sender: 93d2f271-2e53-4e5d-a816-275a3ea34195
Priority: MESSAGE_PRIORITY_HIGH
Content:
You are Explorer M3-2 Circuit Breakers & Pricing.
Working directory: `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m3_2/`
Read `/Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md` before starting work.
Read `/Users/mszdjh3/code/neuri/PROJECT.md`.
Read `/Users/mszdjh3/code/neuri/src/neuri/core/schemas.py` and `src/neuri/core/blackboard.py`.

Your mission:
Investigate and design token/cost tracking and circuit breaker policies in `src/neuri/core/telemetry.py`:
1. Token and cost calculations: tracking cumulative input/output tokens and estimating USD cost using standard model pricing tables (e.g. input $3.00/1M, output $15.00/1M or configurable per model/harness).
2. The 3 circuit breaker policies:
   - `max_node_tokens` (default 64,000 tokens per node)
   - `max_workflow_cost_usd` (default $10.00 per workflow)
   - 3 consecutive identical tool call failures (tripping when the same tool name fails 3 times in a row)
3. Exception hierarchy: `CircuitBreakerTripped(NeuriException)` with `reason: str` and `node_id: str`.
4. Blackboard integration contract: how tripping a breaker transitions node state to `TaskState.WAITING_OPERATOR` and appends diagnostic error feedback to the Blackboard.
Provide exact drop-in designs conforming 100% to Universal Python Standards (`/Users/mszdjh3/.gemini/config/rules/python_standard.md`).
Deliver your findings in `handoff.md` in your working directory and notify the orchestrator via `send_message`.
