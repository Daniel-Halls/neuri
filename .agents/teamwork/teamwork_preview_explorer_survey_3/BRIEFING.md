# BRIEFING — 2026-10-25T15:08:00Z

## Mission
Investigate codebase layout, packaging/dependencies (uv, pyproject.toml), test harness requirements, fixtures (NDJSON stream mocks), Universal Python Standards (python_standard.md) enforcement, and acceptance criteria verification for Neuri Phase 1.

## 🔒 My Identity
- Archetype: explorer
- Roles: Codebase Explorer, Synthesizer
- Working directory: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_survey_3
- Original parent: 93d2f271-2e53-4e5d-a816-275a3ea34195
- Milestone: phase1_survey_3

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Universal Python Standards (python_standard.md) compliance (PEP 8, docstrings, strict type hints, 0 globals, single return, 79-88 char limit)
- Write only to working directory `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_survey_3/`

## Current Parent
- Conversation ID: 93d2f271-2e53-4e5d-a816-275a3ea34195
- Updated: not yet

## Investigation State
- **Explored paths**:
  - `/Users/mszdjh3/code/neuri/.gitignore`
  - `/Users/mszdjh3/code/neuri/LICENSE`
  - `/Users/mszdjh3/code/neuri/README.md`
  - `/Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md`
  - `/Users/mszdjh3/code/neuri/technical_documenation/NEURI_ARCHITECTURE_AND_IMPLEMENTATION_PLAN.md`
  - `/Users/mszdjh3/.gemini/config/rules/python_standard.md`
- **Key findings**:
  - Workspace currently has no `pyproject.toml`, `src/`, `skills/`, or `tests/` directories.
  - `.gitignore` line 2 explicitly ignores `technical_documenation/*`.
  - `run_command` encounters `failed to create PTY: device not configured` on this host. Testing strategy must prioritize headless `CliRunner` and mock/NDJSON streams over live TTY allocation.
  - Packaging requires Python >=3.12, `uv` packaging with `hatchling` backend, and registration of CLI script `neuri = "neuri.cli.main:app"`.
  - Required core dependencies: `pydantic>=2.7`, `typer>=0.12`, `rich>=13.7`, `textual>=0.80`, `pyyaml>=6.0`, `tomli-w>=1.0`, `httpx>=0.27`.
  - Required dev dependencies: `pytest>=8.2`, `pytest-asyncio>=0.24`, `pytest-mock>=3.14`, `ruff>=0.4`, `mypy>=1.10`.
  - Test suite architecture requires 4 tiers: unit tests, adapter replay tests (with NDJSON fixtures), E2E headless CLI tests, and UI tests using Textual `run_test()`.
  - Strict Python standards compliance (`python_standard.md`) should be enforced by an automated AST linter test (`test_standards_compliance.py`) checking PEP 8, strict type hints, mandatory custom docstring template, zero global variables, and single return values.
- **Unexplored areas**: None for survey scope.

## Key Decisions Made
- Established 4-tier test architecture and mock NDJSON fixture schemas for `agy` and `codex`.
- Formulated automated AST verification strategy for Universal Python Standards compliance.
- Mapped inter-module dependencies and sequenced 7-layer implementation roadmap.

## Artifact Index
- DISPATCH.md — Task assignment and input parameters
- BRIEFING.md — Persistent state and identity
- progress.md — Heartbeat and execution step tracker
- handoff.md — Comprehensive survey report (Complete)
