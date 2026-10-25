# Task Assignment: M1 Code & Architecture Review

## Identity
- Role: Reviewer M1-1
- Working directory: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_reviewer_m1_1/
- Project root: /Users/mszdjh3/code/neuri

## Objective
Independently review M1 implementation (`pyproject.toml`, `skills/index.yaml`, `src/neuri/core/schemas.py`, `src/neuri/core/config.py`).
Verify:
1. Correctness, completeness, and interface contracts specified in `PROJECT.md`.
2. Strict compliance with `/Users/mszdjh3/.gemini/config/rules/python_standard.md` (PEP 8, type hints, custom docstrings with Parameters/Returns, zero globals, single return).
3. `SanitizedNeuroHeader` strictly enforces `phi_sanitized: Literal[True] = True`.
4. `skills/index.yaml` is valid YAML and strictly <300 tokens.

## Mandatory Inputs to Read
1. `/Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md`
2. `/Users/mszdjh3/code/neuri/PROJECT.md`
3. `/Users/mszdjh3/.gemini/config/rules/python_standard.md`
4. `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_worker_m1/handoff.md`

## Output Requirements
Write `handoff.md` in your working directory with an explicit verdict: `APPROVE` or `REQUEST_CHANGES`. Include concrete evidence for your verdict.
Send a message to the orchestrator when complete.

## 2026-10-25T15:33:51Z
You are reviewer_m1_1.
Your working directory is: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_reviewer_m1_1/
Please read your task assignment at: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_reviewer_m1_1/DISPATCH.md
Also read:
1. /Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md
2. /Users/mszdjh3/code/neuri/PROJECT.md
3. /Users/mszdjh3/.gemini/config/rules/python_standard.md
4. /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_worker_m1/handoff.md

Review M1 code (pyproject.toml, skills/index.yaml, schemas.py, config.py) for correctness, typing, standards compliance, and interface contracts.
Write your handoff report with verdict APPROVE or REQUEST_CHANGES to /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_reviewer_m1_1/handoff.md and notify the orchestrator.
