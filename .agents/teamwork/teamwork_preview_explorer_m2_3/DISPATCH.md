# Task Assignment: M2 Exploration - Artifacts, Provenance Export & Unit Test Architecture

## Identity
- Role: Explorer M2-3 (Artifacts & Tests)
- Working directory: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m2_3/
- Project root: /Users/mszdjh3/code/neuri

## Objective
Analyze and specify the provenance export, artifact registration, citations ledger, and unit test architecture for Milestone 2:
1. `register_artifact(artifact: RemoteArtifact, workflow_id: str, node_id: str | None = None) -> None`:
   - Enforces unique URI and POSIX path registration.
2. `export_provenance(workflow_id: str, output_path: Path) -> dict[str, Any]`:
   - Serializes workflow summary, all nodes, edges, generated artifacts, and citations into `.neuri/execution_history.json`.
3. Citations ledger tracking:
   - Registration and retrieval of verified DOI / BibTeX entries.
4. Comprehensive test design for `tests/unit/test_blackboard.py`:
   - Database creation, WAL mode verification via `PRAGMA journal_mode`, foreign key enforcement, ready nodes DAG queries, cycle detection, state updates, artifact queries, and provenance export.
5. Ensure 100% compliance with `/Users/mszdjh3/.gemini/config/rules/python_standard.md`.

## Mandatory Inputs to Read
1. `/Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md`
2. `/Users/mszdjh3/code/neuri/PROJECT.md`
3. `/Users/mszdjh3/.gemini/config/rules/python_standard.md`
4. `src/neuri/core/schemas.py`

## Output Requirements
Write `handoff.md` in your working directory with concrete method definitions and test cases.
Do NOT modify source code files.


## 2026-10-25T16:15:19Z
You are explorer_m2_3.
Your working directory is: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m2_3/
Please read your task assignment at: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m2_3/DISPATCH.md
Also read:
1. /Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md
2. /Users/mszdjh3/code/neuri/PROJECT.md
3. /Users/mszdjh3/.gemini/config/rules/python_standard.md
4. src/neuri/core/schemas.py

Focus on artifact registration, citations ledger, provenance export (.neuri/execution_history.json), and unit test suite design (tests/unit/test_blackboard.py).
Write your report to /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m2_3/handoff.md and notify the orchestrator when complete.
Do not modify source code files.
