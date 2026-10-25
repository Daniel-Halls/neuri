# Task Assignment: M1 Adversarial Verification - Schemas & Models

## Identity
- Role: Challenger M1-1
- Working directory: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_challenger_m1_1/
- Project root: /Users/mszdjh3/code/neuri

## Objective
Empirically challenge and stress-test `src/neuri/core/schemas.py`:
1. Write adversarial test scripts in your working directory to probe schemas:
   - Attempt to bypass PHI sanitization (e.g. passing `phi_sanitized=False`, None, strings, or mutant values).
   - Test extreme boundary cases on `SanitizedNeuroHeader`, `RemoteArtifact`, `TaskNode`, `NeuriTaskEnvelope`, `TelemetryEvent`, etc.
   - Test JSON serialization and deserialization roundtrips.
2. Execute your challenge harness and verify whether any invariant breaks.

## Mandatory Inputs to Read
1. `/Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md`
2. `/Users/mszdjh3/code/neuri/PROJECT.md`
3. `/Users/mszdjh3/.gemini/config/rules/python_standard.md`
4. `/Users/mszdjh3/code/neuri/src/neuri/core/schemas.py`

## Output Requirements
Write `handoff.md` in your working directory with an explicit verdict: `APPROVE` (all invariants held against adversarial attacks) or `REQUEST_CHANGES` (vulnerability/bug discovered).
Send a message to the orchestrator when complete.


## 2026-10-25T15:34:32Z
You are challenger_m1_1.
Your working directory is: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_challenger_m1_1/
Please read your task assignment at: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_challenger_m1_1/DISPATCH.md
Also read:
1. /Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md
2. /Users/mszdjh3/code/neuri/PROJECT.md
3. /Users/mszdjh3/.gemini/config/rules/python_standard.md
4. /Users/mszdjh3/code/neuri/src/neuri/core/schemas.py

Empirically challenge and stress-test core schemas (phi_sanitized enforcement, boundary cases, validation exceptions). Write adversarial test harnesses and execute them.
Write your handoff report with verdict APPROVE or REQUEST_CHANGES to /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_challenger_m1_1/handoff.md and notify the orchestrator.
