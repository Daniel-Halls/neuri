# Task Assignment: M2 Forensic Integrity Audit

## Identity
- Role: Forensic Auditor M2
- Working directory: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_auditor_m2/
- Project root: /Users/mszdjh3/code/neuri

## Objective
Perform forensic integrity auditing of Milestone 2:
1. Examine `src/neuri/core/blackboard.py` and `tests/unit/test_blackboard.py`.
2. Integrity checks:
   - Zero hardcoding of test queries or expected outputs in source code.
   - Zero facade or mock implementations (genuine SQLite DDL, queries, transactions, and provenance export).
   - Zero pre-populated artifacts or test bypassing.
   - Verify WAL mode pragma configuration.
   - Verify line lengths $\le 88$ characters across all lines.
   - Verify 100% compliance with `/Users/mszdjh3/.gemini/config/rules/python_standard.md`.

## Mandatory Inputs to Read
1. `/Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md`
2. `/Users/mszdjh3/code/neuri/PROJECT.md`
3. `/Users/mszdjh3/.gemini/config/rules/python_standard.md`
4. `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_worker_m2/handoff.md`

## Output Requirements
Write `handoff.md` in your working directory with an explicit verdict: `CLEAN` or `INTEGRITY VIOLATION`.
Send a message to the orchestrator when complete.


## 2026-10-25T16:35:41Z
You are auditor_m2.
Your working directory is: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_auditor_m2/
Please read your task assignment at: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_auditor_m2/DISPATCH.md
Also read:
1. /Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md
2. /Users/mszdjh3/code/neuri/PROJECT.md
3. /Users/mszdjh3/.gemini/config/rules/python_standard.md
4. /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_worker_m2/handoff.md

Perform forensic integrity auditing of Milestone 2 (SQLite WAL blackboard & provenance store).
Check for hardcoded queries/results, dummy facades, line lengths <= 88, and python standards.
Write your handoff report with verdict CLEAN or INTEGRITY VIOLATION to /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_auditor_m2/handoff.md and notify the orchestrator.
