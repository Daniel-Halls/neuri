# BRIEFING — 2026-10-25T19:37:05Z

## Mission
Investigate and design the exact fix strategy for Observations 1.1, 1.2, and 1.3 from Challenger M2-2 regarding multi-workflow provenance history clobbering, root array structure, and Pydantic round-trip re-hydration of exported nodes and edges.

## 🔒 My Identity
- Archetype: Explorer
- Roles: Read-only investigation, analysis, synthesis, drop-in fix design
- Working directory: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m2_it2_1
- Original parent: 93d2f271-2e53-4e5d-a816-275a3ea34195
- Milestone: M2-It2 (Milestone 2 Iteration 2)

## 🔒 Key Constraints
- Read-only investigation — do NOT implement directly in source files.
- Produce structured report in handoff.md with exact drop-in code snippets conforming 100% to Universal Python Standards.
- Adhere strictly to PEP 8, full type hints, custom Google/NumPy-style docstrings, single return type, no global variables.

## Current Parent
- Conversation ID: 93d2f271-2e53-4e5d-a816-275a3ea34195
- Updated: 2026-10-25T19:37:05Z

## Investigation State
- **Explored paths**:
  - `src/neuri/core/blackboard.py` (lines 2540–2765, `export_provenance`, `_row_to_task_node`, `create_node`)
  - `src/neuri/core/schemas.py` (lines 913–1168, `TaskNode`, `TaskEdge`, `RemoteArtifact`)
  - `tests/unit/test_adversarial_blackboard_provenance.py` (lines 520–770, `TestAdversarialProvenanceExport`)
  - `tests/unit/test_blackboard.py` (lines 1664–1760, `test_export_provenance_full_workflow`)
  - `tests/unit/test_config.py` (line 466, workspace history initialization)
  - `python_standard.md` (PEP 8, docstrings, type annotations, single return type)
- **Key findings**:
  - **Observation 1.1 Root Array & Merge Fix**: `export_provenance` in `blackboard.py` writes a bare dictionary if `output_path` is new, resulting in a JSON Object root `{...}`. Subsequent exports see `raw_text` not starting with `[`, bypass list-merge, and clobber previous workflows. Fix: always parse existing files (promoting single `{...}` dict to list if encountered), merge workflows by `workflow_id` (update in place if exists, append if not), and serialize back as a JSON list root `[...]` on disk, while returning the single workflow dict to callers.
  - **Downstream Unit Test Impact**: `tests/unit/test_blackboard.py:1726-1729` previously asserted `loaded["workflow_id"] == "wf-prov"` on the disk file because it assumed a dict root. With the fix, `loaded` on disk is a list, so `loaded[0]["workflow_id"] == "wf-prov"` must be verified.
  - **Observation 1.2 & 1.3 Schema Re-hydration**: Exported `nodes` and `edges` dictionaries in `export_provenance` omit `workflow_id`, causing Pydantic `missing` validation errors. Exported nodes also include `created_at` and `updated_at`, which are not declared on `TaskNode`, causing `extra_forbidden` errors due to `extra="forbid"`.
  - **TaskNode Schema Strategy**: Rather than stripping timestamps from provenance export (which destroys critical pipeline execution audit trails), `TaskNode` in `schemas.py` should declare `created_at: str | None = None` and `updated_at: str | None = None` with a validator normalizing `datetime` or strings, and `_row_to_task_node` should populate them from SQLite rows.
- **Unexplored areas**: None. Comprehensive evidence chain established.

## Key Decisions Made
- Design drop-in replacement chunk for `export_provenance` in `blackboard.py`.
- Design drop-in updates for `TaskNode` in `schemas.py` and `_row_to_task_node` in `blackboard.py`.
- Design drop-in update for `test_blackboard.py` to prevent regression.

## Artifact Index
- DISPATCH.md — Received dispatch records
- BRIEFING.md — Working memory index
- progress.md — Liveness heartbeat
- handoff.md — Final investigation handoff report
