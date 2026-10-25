# Task Assignment: M2 Adversarial Verification - Artifacts, Citations & Provenance Serialization

## Identity
- Role: Challenger M2-2
- Working directory: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_challenger_m2_2/
- Project root: /Users/mszdjh3/code/neuri

## Objective
Adversarially challenge `src/neuri/core/blackboard.py` artifact registration, citations ledger, and provenance export:
1. Probe artifact uniqueness: duplicate URI registration across nodes, POSIX path collisions on the same host, malformed hashes.
2. Probe citations ledger: duplicate citation keys, missing DOIs, malformed BibTeX entries.
3. Probe provenance export (`.neuri/execution_history.json`): unwriteable directory, concurrent exports, appending to existing history list, JSON round-trip validation.
4. Execute empirical challenge harness in your working directory.

## Mandatory Inputs to Read
1. `/Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md`
2. `/Users/mszdjh3/code/neuri/PROJECT.md`
3. `/Users/mszdjh3/code/neuri/src/neuri/core/blackboard.py`

## Output Requirements
Write `handoff.md` in your working directory with an explicit verdict: `APPROVE` or `REQUEST_CHANGES`. Include concrete empirical execution logs.
Send a message to the orchestrator when complete.


## 2026-10-25T16:35:36Z
[Message] timestamp=2026-10-25T16:35:36Z sender=93d2f271-2e53-4e5d-a816-275a3ea34195 priority=MESSAGE_PRIORITY_HIGH content=You are challenger_m2_2.
Your working directory is: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_challenger_m2_2/
Please read your task assignment at: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_challenger_m2_2/DISPATCH.md
Also read:
1. /Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md
2. /Users/mszdjh3/code/neuri/PROJECT.md
3. src/neuri/core/blackboard.py

Empirically challenge artifact registration, citations ledger, and provenance JSON export (.neuri/execution_history.json).
Write your handoff report with verdict APPROVE or REQUEST_CHANGES to /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_challenger_m2_2/handoff.md and notify the orchestrator.
