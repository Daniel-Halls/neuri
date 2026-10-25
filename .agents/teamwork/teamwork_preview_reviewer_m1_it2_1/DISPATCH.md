# Task Assignment: M1 Iteration 2 Review - Code & Standards Compliance

## Identity
- Role: Reviewer M1-It2-1
- Working directory: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_reviewer_m1_it2_1/
- Project root: /Users/mszdjh3/code/neuri

## Objective
Independently review the remediated Milestone 1 implementation:
1. Examine `src/neuri/core/schemas.py`:
   - Verify `SanitizedNeuroHeader` has `frozen=True, validate_assignment=True, extra="forbid"` and rejects post-instantiation mutation.
   - Verify `NeuriTaskEnvelope` and `TaskNode` support both `role`/`agent_role` and `harness`/`harness_id` aliases seamlessly.
   - Verify `diagnostic_feedback` on `TaskNode` accepts both `str` and `list[str]`.
   - Verify line length across `src/neuri/` does not exceed 88 characters (specifically check line 833 / docstring lines).
   - Verify strict compliance with `/Users/mszdjh3/.gemini/config/rules/python_standard.md` (PEP 8, docstrings with Parameters/Returns, type hints, zero globals, single returns).
2. Examine `tests/unit/test_skills_index.py`:
   - Verify 12 test methods covering YAML structure, 7 neuro skill IDs, modality mapping, triggers, and <300 token budget.

## Mandatory Inputs to Read
1. `/Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md`
2. `/Users/mszdjh3/code/neuri/PROJECT.md`
3. `/Users/mszdjh3/.gemini/config/rules/python_standard.md`
4. `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_worker_m1_it2/handoff.md`

## Output Requirements
Write `handoff.md` in your working directory with an explicit verdict: `APPROVE` or `REQUEST_CHANGES`.
Send a message to the orchestrator when complete.

## 2026-10-25T16:06:37Z
Sender: 93d2f271-2e53-4e5d-a816-275a3ea34195
Priority: MESSAGE_PRIORITY_HIGH
Content:
You are reviewer_m1_it2_1.
Your working directory is: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_reviewer_m1_it2_1/
Please read your task assignment at: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_reviewer_m1_it2_1/DISPATCH.md
Also read:
1. /Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md
2. /Users/mszdjh3/code/neuri/PROJECT.md
3. /Users/mszdjh3/.gemini/config/rules/python_standard.md
4. /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_worker_m1_it2/handoff.md

Review M1 Iteration 2 code and standards. Write handoff.md with verdict APPROVE or REQUEST_CHANGES and notify the orchestrator.
