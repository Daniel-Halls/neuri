# Task Assignment: M1 Adversarial Verification - Two-Tier Config & Workspace Scaffolding

## Identity
- Role: Challenger M1-2
- Working directory: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_challenger_m1_2/
- Project root: /Users/mszdjh3/code/neuri

## Objective
Empirically challenge and stress-test `src/neuri/core/config.py` and `skills/index.yaml`:
1. Write adversarial test scripts in your working directory to probe configuration:
   - Deep merge boundary collisions, nested type mismatches, empty/malformed TOML files.
   - Concurrent `init_workspace` invocations and SQLite WAL database creation.
   - Token counting of `skills/index.yaml` under different tokenizers (OpenAI `cl100k_base`, word count, etc.) to ensure it is strictly <300 tokens.
2. Execute your challenge harness and document results.

## Mandatory Inputs to Read
1. `/Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md`
2. `/Users/mszdjh3/code/neuri/PROJECT.md`
3. `/Users/mszdjh3/.gemini/config/rules/python_standard.md`
4. `/Users/mszdjh3/code/neuri/src/neuri/core/config.py`
5. `/Users/mszdjh3/code/neuri/skills/index.yaml`

## Output Requirements
Write `handoff.md` in your working directory with an explicit verdict: `APPROVE` or `REQUEST_CHANGES`. Include empirical execution logs.
Send a message to the orchestrator when complete.

## 2026-10-25T15:34:37Z
Sender: 93d2f271-2e53-4e5d-a816-275a3ea34195
You are challenger_m1_2.
Your working directory is: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_challenger_m1_2/
Please read your task assignment at: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_challenger_m1_2/DISPATCH.md
Also read:
1. /Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md
2. /Users/mszdjh3/code/neuri/PROJECT.md
3. /Users/mszdjh3/.gemini/config/rules/python_standard.md
4. /Users/mszdjh3/code/neuri/src/neuri/core/config.py
5. /Users/mszdjh3/code/neuri/skills/index.yaml

Empirically challenge two-tier config loading, workspace scaffolding, SQLite WAL creation, and catalog token limits. Write adversarial test harnesses and execute them.
Write your handoff report with verdict APPROVE or REQUEST_CHANGES to /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_challenger_m1_2/handoff.md and notify the orchestrator.
