# Task Assignment: M1 Exploration - Core Schemas Specification

## Identity
- Role: Explorer M1-2
- Working directory: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m1_2/
- Project root: /Users/mszdjh3/code/neuri

## Objective
Analyze and recommend the exact implementation strategy for `src/neuri/core/schemas.py`:
- All 13 Pydantic v2 data models: `ModalityType`, `SanitizedNeuroHeader` (enforcing `phi_sanitized: Literal[True]`), `RemoteArtifact`, `TaskState`, `TaskNode`, `TaskEdge`, `NeuriTaskEnvelope`, `NeuriTaskResult`, `TelemetryEvent`, `NiiVueLayerSpec`, `NiiVueSceneSpec`, `ChatRole`, `ChatTurn`, and `SessionEvent`.
- 100% strict compliance with `/Users/mszdjh3/.gemini/config/rules/python_standard.md`:
  - PEP 8 naming and formatting (snake_case, PascalCase, 4 spaces, 79-88 char limit).
  - Explicit type hints on all parameters and returns.
  - Custom docstring format with `Parameters` and `Returns` on EVERY function/method/class.
  - Zero global variables. Single return type/variable. Single responsibility.

## Mandatory Inputs to Read
1. `/Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md`
2. `/Users/mszdjh3/code/neuri/PROJECT.md`
3. `/Users/mszdjh3/code/neuri/technical_documenation/NEURI_ARCHITECTURE_AND_IMPLEMENTATION_PLAN.md`
4. `/Users/mszdjh3/.gemini/config/rules/python_standard.md`
5. `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_spec_miner_survey_1/handoff.md`

## Output Requirements
Write `handoff.md` in your working directory with concrete class definitions, docstrings, field validations, and edge case tests.
Do NOT modify source code files.

## 2026-10-25T15:15:53Z
You are explorer_m1_2.
Your working directory is: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m1_2/
Please read your task assignment at: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m1_2/DISPATCH.md
Also read:
1. /Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md
2. /Users/mszdjh3/code/neuri/PROJECT.md
3. /Users/mszdjh3/code/neuri/technical_documenation/NEURI_ARCHITECTURE_AND_IMPLEMENTATION_PLAN.md
4. /Users/mszdjh3/.gemini/config/rules/python_standard.md
5. /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_spec_miner_survey_1/handoff.md

Focus on src/neuri/core/schemas.py (all 13 models, strict typing, docstrings, phi_sanitized Literal[True]).
Write your detailed findings to /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m1_2/handoff.md and notify the orchestrator when done.
Do not modify source code files.
