# Task Assignment: E2E Test Suite Framework & Compliance Validator

## Identity
- Role: E2E Test Suite Architect
- Working directory: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_test_writer_e2e/
- Project root: /Users/mszdjh3/code/neuri

## Objective
Author the foundational test fixtures, offline stream replays, and the automated AST compliance test suite for Phase 1 per `TEST_INFRA.md`.

## Mandatory Inputs to Read
1. `/Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md`
2. `/Users/mszdjh3/code/neuri/PROJECT.md`
3. `/Users/mszdjh3/code/neuri/TEST_INFRA.md`
4. `/Users/mszdjh3/.gemini/config/rules/python_standard.md`
5. `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_survey_3/handoff.md`

## File Ownership (Exclusively owned by this test writer)
- `tests/fixtures/agy_stream_sample.ndjson`
- `tests/fixtures/agy_breaker_sample.ndjson`
- `tests/fixtures/codex_stream_sample.ndjson`
- `tests/fixtures/codex_error_sample.ndjson`
- `tests/unit/test_standards_compliance.py` (AST-based checker enforcing PEP 8, docstrings with Parameters/Returns, strict type hints, 0 globals, single return on all `src/neuri/` files)

## Deliverables
1. Author the 4 NDJSON stream fixture files in `tests/fixtures/` with realistic chunk streams including `<thinking>` tags, tool invocations, token usages, and circuit breaker trigger conditions.
2. Author `tests/unit/test_standards_compliance.py` that inspects Python source files in `src/neuri` via Python AST, verifying 100% compliance with `python_standard.md`.
3. Write `handoff.md` in `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_test_writer_e2e/handoff.md` and message the orchestrator when finished.


## 2026-10-25T15:23:41Z
[Message] timestamp=2026-10-25T15:23:41Z sender=93d2f271-2e53-4e5d-a816-275a3ea34195 priority=MESSAGE_PRIORITY_HIGH content=You are test_writer_e2e.
Your working directory is: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_test_writer_e2e/
Please read your task assignment at: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_test_writer_e2e/DISPATCH.md
Also read:
1. /Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md
2. /Users/mszdjh3/code/neuri/PROJECT.md
3. /Users/mszdjh3/code/neuri/TEST_INFRA.md
4. /Users/mszdjh3/.gemini/config/rules/python_standard.md
5. /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_survey_3/handoff.md

Your exclusive write targets:
- tests/fixtures/agy_stream_sample.ndjson
- tests/fixtures/agy_breaker_sample.ndjson
- tests/fixtures/codex_stream_sample.ndjson
- tests/fixtures/codex_error_sample.ndjson
- tests/unit/test_standards_compliance.py

Write your handoff report to /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_test_writer_e2e/handoff.md and notify the orchestrator when complete.
