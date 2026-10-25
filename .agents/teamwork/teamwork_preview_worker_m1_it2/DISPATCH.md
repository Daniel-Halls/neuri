# Task Assignment: M1 Iteration 2 Implementation (Remediation)

## 2026-10-25T15:53:55Z

## Identity
- Role: Worker M1-It2
- Working directory: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_worker_m1_it2/
- Project root: /Users/mszdjh3/code/neuri

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Mandatory Inputs to Read
1. `/Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md`
2. `/Users/mszdjh3/code/neuri/PROJECT.md`
3. `/Users/mszdjh3/.gemini/config/rules/python_standard.md`
4. `/Users/mszdjh3/code/neuri/.agents/teamwork/orchestrator_1/GATE_STATUS.md`
5. `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m1_it2_1/handoff.md`
6. `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m1_it2_2/handoff.md`
7. `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m1_it2_3/handoff.md`
8. Proposed files in `teamwork_preview_explorer_m1_it2_3/`:
   - `proposed_test_skills_index.py`
   - `proposed_test_schemas_adversarial_extensions.py`

## File Ownership (Exclusively owned by this worker)
- `src/neuri/core/schemas.py`
- `tests/unit/test_skills_index.py`
- `tests/unit/test_schemas_adversarial.py`
- `tests/unit/test_schemas.py`

## Implementation Tasks
1. **`src/neuri/core/schemas.py`**:
   - `SanitizedNeuroHeader`: Add `ConfigDict(frozen=True, validate_assignment=True, extra="forbid")` to prevent post-instantiation mutation. Add positive bounds validation on `voxel_sizes_mm` (`v > 0`), `tr_seconds > 0`, `sampling_freq_hz > 0`, and finite real numbers in `value_range` (disallowing NaN/Inf).
   - `NeuriTaskEnvelope` & `TaskNode`: Add alias normalization and properties for `role`/`agent_role` and `harness`/`harness_id` per `explorer_m1_it2_2/handoff.md`.
   - `TaskNode`: Harmonize `diagnostic_feedback` to accept `list[str] | str | None` and normalize to `list[str]`.
   - `RemoteArtifact`: Ensure `posix_path` is absolute (`/` prefix) and consistent with `uri`.
   - Line 833: Wrap the docstring line in `TelemetryEvent` so all lines in `schemas.py` are strictly $\le 88$ characters.
2. **`tests/unit/test_skills_index.py`**:
   - Write `tests/unit/test_skills_index.py` copying the contents of `teamwork_preview_explorer_m1_it2_3/proposed_test_skills_index.py`.
3. **`tests/unit/test_schemas_adversarial.py`**:
   - Append the adversarial test extensions from `proposed_test_schemas_adversarial_extensions.py` into `tests/unit/test_schemas_adversarial.py`.
4. **Python Standards Compliance**:
   - Ensure 100% adherence to `/Users/mszdjh3/.gemini/config/rules/python_standard.md` (PEP 8, docstrings with Parameters/Returns, type hints, zero globals, single return).

## Verification & Handoff
1. Verify with pytest (e.g. `python -m pytest tests/unit/ -v`).
2. Verify AST compliance passes cleanly (`python -m pytest tests/unit/test_standards_compliance.py -v`).
3. Write `handoff.md` in your working directory and notify the orchestrator when finished.
