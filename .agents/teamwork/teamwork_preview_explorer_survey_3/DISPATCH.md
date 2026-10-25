# Task Assignment: Survey Codebase Layout, Dependencies, Python Standards & Testing Infrastructure (R8, Acceptance Criteria, Edge Cases)

## Identity
- Role: Codebase Explorer (Survey 3)
- Working directory: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_survey_3/
- Project root: /Users/mszdjh3/code/neuri

## Objective
Investigate the existing workspace files, configuration, dependencies (`uv`, `pyproject.toml`), test harness requirements, Universal Python Standards (`python_standard.md`) enforcement, and integration verification requirements across the entire Phase 1 scope.

## Mandatory Inputs to Read
1. `/Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md`
2. `technical_documenation/NEURI_ARCHITECTURE_AND_IMPLEMENTATION_PLAN.md`
3. `phase1_implementation_plan.md`
4. `/Users/mszdjh3/.gemini/config/rules/python_standard.md`
5. Existing repository files in `/Users/mszdjh3/code/neuri`

## Focus Areas
- Codebase layout: inspect what files currently exist in `/Users/mszdjh3/code/neuri`, verify git status or directory tree.
- Dependencies & build setup: `pyproject.toml`, `uv.lock`, required packages (`pydantic>=2.7`, `typer>=0.12`, `rich>=13.7`, `textual>=0.80`, `pyyaml>=6.0`, `tomli-w>=1.0`, `httpx>=0.27`, `pytest>=8.2`, `pytest-asyncio>=0.24`), CLI entry points.
- Testing infrastructure: pytest configuration, test directory layout (`tests/unit/`, `tests/e2e/`, `tests/fixtures/`), NDJSON replay fixtures for agy and codex, test runners.
- Universal Python Standards (R8): docstring template requirements, PEP 8, line length (79-88), strict typing, zero globals, single return.
- Acceptance criteria and verification checklist mapping.

## Deliverables
Write a comprehensive report to `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_survey_3/handoff.md` detailing:
1. Current state of repository (existing files, missing directories/files).
2. Dependency and packaging requirements.
3. Test suite architecture and verification strategy (test tiers 1-4, fixtures needed).
4. Compliance checklist for `/Users/mszdjh3/.gemini/config/rules/python_standard.md`.
5. Dependencies and sequencing risks across modules.
When done, message the orchestrator with a summary and link to handoff.md.

## 2026-10-25T15:07:43Z
From: 93d2f271-2e53-4e5d-a816-275a3ea34195
You are explorer_survey_3.
Your working directory is: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_survey_3/
Please read your task assignment at: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_survey_3/DISPATCH.md
Also read:
1. /Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md
2. technical_documenation/NEURI_ARCHITECTURE_AND_IMPLEMENTATION_PLAN.md
3. phase1_implementation_plan.md
4. /Users/mszdjh3/.gemini/config/rules/python_standard.md
5. Existing repository files in /Users/mszdjh3/code/neuri

Focus on Codebase layout, dependencies (uv, pyproject.toml), test harness requirements, fixtures (NDJSON stream mocks), Universal Python Standards (python_standard.md) enforcement, and acceptance criteria verification.
Write your detailed report to /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_survey_3/handoff.md and update progress.md in your working directory.
When finished, send a message to the orchestrator with your findings.

