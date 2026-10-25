# Task Assignment: Survey Harness Adapters, Pre-flight Hook, DAG Orchestrator, CLI & Terminal Chat UI (R4, R5, R7)

## Identity
- Role: Specification Miner (Survey 2)
- Working directory: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_spec_miner_survey_2/
- Project root: /Users/mszdjh3/code/neuri

## Objective
Map the full functional specification, feature inventory, adapter protocols, CLI arguments, Textual UI layout/events, preflight rules, and DAG execution mechanics for Neuri Phase 1.

## Mandatory Inputs to Read
1. `/Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md`
2. `technical_documenation/NEURI_ARCHITECTURE_AND_IMPLEMENTATION_PLAN.md`
3. `phase1_implementation_plan.md`
4. `/Users/mszdjh3/.gemini/config/rules/python_standard.md`

## Focus Areas
- R4: BaseHarnessAdapter (`base.py`), Tier-1 `AntigravityAdapter` (`antigravity.py`), Tier-1 `CodexAdapter` (`codex.py`), Tier-2 stubs (`opencode.py`, `openclaw.py`, `ollama_local.py`), and `AdapterRegistry` (`registry.py`).
- R5: Pre-Flight Hook (`preflight.py`, zero token cost, PHI sanitization, coordinate space alignment, artifact existence) and DAG Orchestrator (`orchestrator.py`, topological execution, bounded auto-retry N=2, diagnostic feedback, WAITING_OPERATOR transitions).
- R7: CLI Entrypoint (`main.py`, headless vs interactive, `--print`, `-p`, `--dry-run`), and Textual Terminal Chat UI (`terminal_chat.py`, banner, collapsible thinking, DAG badge widgets, prompt autocompletion, status bar).

## Deliverables
Write a comprehensive report to `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_spec_miner_survey_2/handoff.md` detailing:
1. Complete inventory of features, functions, and classes for R4, R5, R7.
2. Required interface signatures, parameters, CLI flags, Textual widget structure, and return types.
3. NDJSON stream replay requirements and mocking strategy for Antigravity & Codex adapters.
4. Edge cases, error handling, and acceptance criteria.
5. Conformance constraints per Python standard rules.
When done, message the orchestrator with a summary and link to handoff.md.


## 2026-10-25T15:07:38Z
You are spec_miner_survey_2.
Your working directory is: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_spec_miner_survey_2/
Please read your task assignment at: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_spec_miner_survey_2/DISPATCH.md
Also read:
1. /Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md
2. technical_documenation/NEURI_ARCHITECTURE_AND_IMPLEMENTATION_PLAN.md
3. phase1_implementation_plan.md
4. /Users/mszdjh3/.gemini/config/rules/python_standard.md

Focus on R4 (BaseHarnessAdapter, Tier-1 AntigravityAdapter, Tier-1 CodexAdapter, Tier-2 adapters, AdapterRegistry), R5 (Pre-Flight Hook & DAG Orchestrator), and R7 (CLI Entrypoint & Textual Terminal Chat UI).
Write your detailed report to /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_spec_miner_survey_2/handoff.md and update progress.md in your working directory.
When finished, send a message to the orchestrator with your findings.
