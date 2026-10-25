# Task Assignment: M1 Exploration - Two-Tier Config & Unit Test Architecture

## Identity
- Role: Explorer M1-3
- Working directory: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m1_3/
- Project root: /Users/mszdjh3/code/neuri

## Objective
Analyze and recommend the exact implementation strategy for:
1. `src/neuri/core/config.py`:
   - Two-tier configuration loader (`load_config`) merging `~/.neuri/config.toml` defaults with `.neuri/neuri.toml` overrides.
   - Project workspace initializer (`init_workspace`) scaffolding `.neuri/` (`neuri.toml`, `state.db`, `references.bib`, `execution_history.json`, `qa_snapshots/`).
   - Configuration dataclasses/Pydantic models (`NeuriConfig`, `WorkspaceConfig`, `HarnessRoutingConfig`, `BudgetConfig`).
   - 100% compliance with `/Users/mszdjh3/.gemini/config/rules/python_standard.md`.
2. Unit tests for M1 (`tests/unit/test_schemas.py`, `tests/unit/test_config.py`):
   - Comprehensive test cases covering happy path, validation failures (e.g. `phi_sanitized=False`), missing config files, corrupted TOML, and workspace initialization.

## Mandatory Inputs to Read
1. `/Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md`
2. `/Users/mszdjh3/code/neuri/PROJECT.md`
3. `/Users/mszdjh3/code/neuri/technical_documenation/NEURI_ARCHITECTURE_AND_IMPLEMENTATION_PLAN.md`
4. `/Users/mszdjh3/.gemini/config/rules/python_standard.md`
5. `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_spec_miner_survey_1/handoff.md`

## Output Requirements
Write `handoff.md` in your working directory with concrete function definitions, config merge algorithm, and test cases.
Do NOT modify source code files.


## 2026-10-25T15:15:58Z
You are explorer_m1_3.
Your working directory is: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m1_3/
Please read your task assignment at: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m1_3/DISPATCH.md
Also read:
1. /Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md
2. /Users/mszdjh3/code/neuri/PROJECT.md
3. /Users/mszdjh3/code/neuri/technical_documenation/NEURI_ARCHITECTURE_AND_IMPLEMENTATION_PLAN.md
4. /Users/mszdjh3/.gemini/config/rules/python_standard.md
5. /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_spec_miner_survey_1/handoff.md

Focus on src/neuri/core/config.py (two-tier config loader, init_workspace) and unit test specifications (tests/unit/test_schemas.py, tests/unit/test_config.py).
Write your detailed findings to /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m1_3/handoff.md and notify the orchestrator when done.
Do not modify source code files.
