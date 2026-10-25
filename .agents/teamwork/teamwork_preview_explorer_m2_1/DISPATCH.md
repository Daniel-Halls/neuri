# Task Assignment: M2 Exploration - DDL Schemas, SQLite WAL & Connection Management

## Identity
- Role: Explorer M2-1 (DDL & WAL)
- Working directory: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m2_1/
- Project root: /Users/mszdjh3/code/neuri

## Objective
Analyze and specify the SQLite DDL, indexing, and connection management for `src/neuri/core/blackboard.py`:
1. SQLite WAL mode configuration:
   - `PRAGMA journal_mode=WAL;`
   - `PRAGMA foreign_keys=ON;`
   - `PRAGMA busy_timeout=5000;`
   - `PRAGMA synchronous=NORMAL;`
2. DDL specifications for all 7 core tables:
   - `workflows` (workflow_id, prompt, status, created_at, updated_at, total_tokens, estimated_cost_usd)
   - `task_nodes` (node_id, workflow_id, agent_role, harness_id, state, envelope_json, diagnostic_feedback_json, created_at, updated_at, completed_at)
   - `task_edges` (workflow_id, parent_node_id, child_node_id)
   - `remote_artifacts` (uri, workflow_id, node_id, host, posix_path, modality, space, header_json, sha256, created_at)
   - `remote_jobs` (job_id, node_id, host, scheduler_type, scheduler_job_id, status_uri, created_at, updated_at)
   - `telemetry_events` (event_id, workflow_id, node_id, timestamp, event_type, thinking_text, input_tokens, output_tokens, cost_usd, tool_name, tool_status, payload_json)
   - `citations_ledger` (citation_key, doi, pmid, title, authors, year, bibtex, verified, created_at)
3. Ensure 100% compliance with `/Users/mszdjh3/.gemini/config/rules/python_standard.md`.

## Mandatory Inputs to Read
1. `/Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md`
2. `/Users/mszdjh3/code/neuri/PROJECT.md`
3. `/Users/mszdjh3/.gemini/config/rules/python_standard.md`
4. `/Users/mszdjh3/code/neuri/technical_documenation/NEURI_ARCHITECTURE_AND_IMPLEMENTATION_PLAN.md` (lines 366-376)
5. `src/neuri/core/schemas.py`

## Output Requirements
Write `handoff.md` in your working directory with concrete DDL strings, class architecture, and methods.
Do NOT modify source code files.

## 2026-10-25T16:15:08Z
[Message] sender=93d2f271-2e53-4e5d-a816-275a3ea34195
You are explorer_m2_1.
Your working directory is: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m2_1/
Please read your task assignment at: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m2_1/DISPATCH.md
Also read:
1. /Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md
2. /Users/mszdjh3/code/neuri/PROJECT.md
3. /Users/mszdjh3/.gemini/config/rules/python_standard.md
4. technical_documenation/NEURI_ARCHITECTURE_AND_IMPLEMENTATION_PLAN.md (lines 366-376)
5. src/neuri/core/schemas.py

Focus on SQLite DDL schemas for all 7 tables, WAL mode, foreign keys, and indexes for blackboard.py.
Write your report to /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m2_1/handoff.md and notify the orchestrator when complete.
Do not modify source code files.
