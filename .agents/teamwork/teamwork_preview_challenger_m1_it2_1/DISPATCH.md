# Task Assignment: M1 Iteration 2 Adversarial Stress Testing - Schemas & Invariants

## Identity
- Role: Challenger M1-It2-1
- Working directory: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_challenger_m1_it2_1/
- Project root: /Users/mszdjh3/code/neuri

## Objective
Adversarially challenge the remediated `src/neuri/core/schemas.py`:
1. Verify mutation attacks fail: instantiate `SanitizedNeuroHeader` and attempt `header.phi_sanitized = False` — assert `pydantic.ValidationError` or `TypeError` is raised.
2. Verify alias attacks: instantiate `NeuriTaskEnvelope` using both `role` and `agent_role`, `harness` and `harness_id` — assert both yield identical attribute values.
3. Verify boundary attacks: negative voxel sizes, zero sampling frequencies, NaN in value range — assert all are cleanly rejected.
4. Execute empirical verification scripts in your working directory.

## Mandatory Inputs to Read
1. `/Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md`
2. `/Users/mszdjh3/code/neuri/PROJECT.md`
3. `/Users/mszdjh3/code/neuri/src/neuri/core/schemas.py`
4. `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_worker_m1_it2/handoff.md`

## Output Requirements
Write `handoff.md` in your working directory with an explicit verdict: `APPROVE` or `REQUEST_CHANGES`. Include concrete execution results.
Send a message to the orchestrator when complete.


## 2026-10-25T16:06:48Z
You are challenger_m1_it2_1.
Your working directory is: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_challenger_m1_it2_1/
Please read your task assignment at: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_challenger_m1_it2_1/DISPATCH.md
Also read:
1. /Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md
2. /Users/mszdjh3/code/neuri/PROJECT.md
3. /Users/mszdjh3/code/neuri/src/neuri/core/schemas.py
4. /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_worker_m1_it2/handoff.md

Empirically challenge the remediated schemas (immutability, positive bounds, NaN rejection, alias normalization). Write handoff.md with verdict APPROVE or REQUEST_CHANGES and notify the orchestrator.
