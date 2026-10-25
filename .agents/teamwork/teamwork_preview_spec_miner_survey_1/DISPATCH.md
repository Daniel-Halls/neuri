# Task Assignment: Survey Core Architecture, Schemas, Blackboard, Telemetry & Session Engine (R1, R2, R3, R6)

## Identity
- Role: Specification Miner (Survey 1)
- Working directory: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_spec_miner_survey_1/
- Project root: /Users/mszdjh3/code/neuri

## Objective
Map the full functional specification, feature inventory, schema details, data models, state transitions, circuit breaker logic, slash commands, and session event streaming for Neuri Phase 1.

## Mandatory Inputs to Read
1. `/Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md`
2. `technical_documenation/NEURI_ARCHITECTURE_AND_IMPLEMENTATION_PLAN.md`
3. `phase1_implementation_plan.md`
4. `/Users/mszdjh3/.gemini/config/rules/python_standard.md`

## Focus Areas
- R1: Package Scaffolding, Schemas (`schemas.py`), Two-Tier Config (`config.py`), and compact catalog `skills/index.yaml` (<300 tokens, 7 neuro skill packs).
- R2: SQLite WAL Blackboard & Provenance Store (`blackboard.py`, 7 core tables, atomic CRUD, topological DAG queries, provenance history).
- R3: TelemetryTap & Circuit Breakers (`telemetry.py`, event normalization, `<thinking>` parsing, hard limits, failure breakers).
- R6: Slash Commands (`slash_commands.py`) and UI-agnostic Session Engine (`session.py`, `SessionEvent` streams).

## Deliverables
Write a comprehensive report to `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_spec_miner_survey_1/handoff.md` detailing:
1. Complete inventory of features, functions, and data models for R1, R2, R3, R6.
2. Required interface signatures, parameters, return types, and schemas.
3. Edge cases, error handling, and acceptance criteria.
4. Conformance constraints per Python standard rules.
When done, message the orchestrator with a summary and link to handoff.md.
