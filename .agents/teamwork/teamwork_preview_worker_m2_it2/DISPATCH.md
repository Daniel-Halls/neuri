## 2026-10-25T19:38:45Z
You are Worker M2-It2.
Working directory: `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_worker_m2_it2/`

MANDATORY: Read `/Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md` before starting work.
Read `/Users/mszdjh3/code/neuri/PROJECT.md`.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Read the 3 Explorer handoff reports:
- `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m2_it2_1/handoff.md` (Provenance export root list, merge logic, node/edge deserialization, TaskNode created_at/updated_at)
- `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m2_it2_2/handoff.md` (Artifact cross-workflow check, SHA-256 pattern, IntegrityError wrapping, fixture expansion)
- `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m2_it2_3/handoff.md` (Citations year error wrapping, BibTeX syntax validation, test updates)

YOUR WRITE OWNERSHIP:
You own exclusively:
- `src/neuri/core/schemas.py`
- `src/neuri/core/blackboard.py`
- `tests/conftest.py`
- `tests/unit/test_schemas.py`
- `tests/unit/test_schemas_adversarial.py`
- `tests/unit/test_blackboard.py`
- `tests/unit/test_adversarial_blackboard_provenance.py`

Apply the exact drop-in implementations and test adjustments:
1. `src/neuri/core/schemas.py`:
   - In `RemoteArtifact`: add `pattern=r"^[0-9a-f]{64}$"` to `sha256_header`.
   - In `TaskNode`: add `created_at: str | None = Field(default=None, ...)` and `updated_at: str | None = Field(default=None, ...)`, docstrings, and `normalize_timestamp_str` validator.
2. `src/neuri/core/blackboard.py`:
   - Import `re`.
   - In `BlackboardSchema.CREATE_REMOTE_ARTIFACTS_TABLE`: add `CHECK (length(sha256) == 64 AND NOT (sha256 GLOB '*[^0-9a-f]*'))`.
   - In `register_artifact`:
     - Add proactive `artifact_id` check.
     - Add `sha256_header` regex validation (`^[0-9a-f]{64}$`).
     - Check `WHERE node_id = ? AND workflow_id = ?` for target_node_id, raising `NodeNotFoundError`.
     - Wrap SQL execute in `try ... except sqlite3.IntegrityError as exc: raise ArtifactRegistrationError(...) from exc`.
   - In `register_citation`:
     - Add internal helper `_validate_bibtex_syntax(self, bibtex: str, citation_key: str) -> None:` verifying non-empty, `@`, `{`, matching `}`.
     - Wrap SQL execute in `try ... except sqlite3.IntegrityError as exc: raise BlackboardError(...) from exc`.
   - In `export_provenance`:
     - Add `"workflow_id": workflow_id` to both `nodes_data.append` and `edges_data`.
     - Add `created_at` and `updated_at` to `_row_to_task_node`.
     - Rewrite history file merge logic so `output_path` is ALWAYS serialized as a JSON list `[...]` at root, parsing existing files (supporting both lists and single dicts), replacing matching `workflow_id` or appending.
3. Test alignment:
   - `tests/conftest.py`: update line 83 to 64-char sha256 (`"abcdef1234567890" * 4`).
   - `tests/unit/test_schemas.py`: update lines 175 & 210 to 64-char sha256.
   - `tests/unit/test_schemas_adversarial.py`: update line 418 to 64-char sha256.
   - `tests/unit/test_blackboard.py`: update line 1729 to `loaded_history[0]["workflow_id"] == "wf-prov"`.
   - `tests/unit/test_adversarial_blackboard_provenance.py`:
     - `test_artifact_cross_workflow_node_foreign_key_behavior` asserts `NodeNotFoundError`.
     - `test_artifact_malformed_sha256_hash` asserts `ValidationError`.
     - `test_citation_year_check_constraint_boundary` asserts `BlackboardError`.
     - `test_citation_malformed_bibtex` asserts `BlackboardError`.

Universal Python Standards (`/Users/mszdjh3/.gemini/config/rules/python_standard.md`):
- Strict PEP 8, 4 spaces, line lengths <= 88 characters.
- Complete type annotations on all parameters and single return.
- Preferred docstrings with `Parameters` and `Returns` blocks on all classes and functions.
- ZERO global variables.

Verify with:
`uv run pytest tests/unit/ -v`
`uv run pytest tests/unit/test_standards_compliance.py -v`

Write your handoff report to `handoff.md` in your working directory and notify the orchestrator via `send_message`.
