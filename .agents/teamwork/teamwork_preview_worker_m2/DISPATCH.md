# Task Assignment: Implement Milestone 2 (SQLite WAL Blackboard & Provenance Store)

## Identity
- Role: M2 Implementation Worker
- Working directory: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_worker_m2/
- Project root: /Users/mszdjh3/code/neuri

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Mandatory Inputs to Read
1. `/Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md`
2. `/Users/mszdjh3/code/neuri/PROJECT.md`
3. `/Users/mszdjh3/.gemini/config/rules/python_standard.md`
4. `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m2_1/handoff.md`
5. `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m2_2/handoff.md`
6. `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m2_3/handoff.md`
7. `src/neuri/core/schemas.py`

## File Ownership (Exclusively owned by this worker)
- `src/neuri/core/blackboard.py`
- `tests/unit/test_blackboard.py`

## Implementation Scope
1. **`src/neuri/core/blackboard.py`**:
   - Connection manager & Pragmas: `PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON; PRAGMA busy_timeout=5000; PRAGMA synchronous=NORMAL;`.
   - Core tables & indexes (all 7 tables: `workflows`, `task_nodes`, `task_edges`, `remote_artifacts`, `remote_jobs`, `telemetry_events`, `citations_ledger`).
   - Atomic CRUD: workflows, task nodes, task edges.
   - Topological DAG queries: `get_ready_nodes(workflow_id: str) -> list[TaskNode]` returning `PENDING` nodes whose parents are all `COMPLETED`.
   - DAG cycle detection: incremental reachability check before edge insertion.
   - State machine & transitions: `update_node_state(node_id: str, state: TaskState, diagnostic_feedback: str | None = None) -> None`.
   - Artifact registration: `register_artifact(artifact: RemoteArtifact, workflow_id: str, node_id: str | None = None) -> None`.
   - Citations ledger: `register_citation`, `list_citations`.
   - Provenance export: `export_provenance(workflow_id: str, output_path: Path) -> dict[str, Any]` writing `.neuri/execution_history.json`.
2. **`tests/unit/test_blackboard.py`**:
   - Comprehensive unit test suite covering WAL mode, tables, DAG queries, cycle detection, state updates, artifact registration, remote jobs, citations, and provenance export.
3. **Universal Python Standards**:
   - 100% compliance with `/Users/mszdjh3/.gemini/config/rules/python_standard.md`:
     - Strict PEP 8, line lengths $\le 88$ characters.
     - Explicit type hints on all arguments, methods, and returns.
     - Custom docstrings with `Parameters` and `Returns` blocks on every class, method, and function.
     - Zero global variables. Single return type/variable. Single responsibility.

## Verification & Handoff
1. Verify with pytest (`python -m pytest tests/unit/test_blackboard.py -v`).
2. Verify standards compliance passes cleanly (`python -m pytest tests/unit/test_standards_compliance.py -v`).
3. Write `handoff.md` in your working directory and notify the orchestrator when finished.

## 2026-10-25T16:24:15Z
[Message] timestamp=2026-10-25T16:24:15Z sender=93d2f271-2e53-4e5d-a816-275a3ea34195 priority=MESSAGE_PRIORITY_HIGH content=You are worker_m2.
Your working directory is: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_worker_m2/
Please read your task assignment at: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_worker_m2/DISPATCH.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Read:
1. /Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md
2. /Users/mszdjh3/code/neuri/PROJECT.md
3. /Users/mszdjh3/.gemini/config/rules/python_standard.md
4. /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m2_1/handoff.md
5. /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m2_2/handoff.md
6. /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m2_3/handoff.md
7. src/neuri/core/schemas.py

Files you exclusively own:
- src/neuri/core/blackboard.py
- tests/unit/test_blackboard.py

Ensure 100% strict compliance with python_standard.md (line lengths <= 88, docstrings with Parameters/Returns, type hints, zero globals, single return).
Run tests to verify passing execution, write your handoff report to /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_worker_m2/handoff.md, and message the orchestrator when finished.
