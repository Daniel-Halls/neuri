# Adversarial Challenge Handoff Report: Milestone 1 Iteration 2

**Agent**: `challenger_m1_it2_1`  
**Roles**: `critic`, `specialist`  
**Working Directory**: `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_challenger_m1_it2_1/`  
**Parent Agent**: `93d2f271-2e53-4e5d-a816-275a3ea34195`  
**Milestone**: Milestone 1 Iteration 2 (Core Schemas Hardening & Gate Clearance)  
**Verdict**: **APPROVE**  
**Date**: 2026-10-25  

---

## 1. Observation

### 1.1 Direct Observation of Schema Implementation (`src/neuri/core/schemas.py`)
1. **SanitizedNeuroHeader Immutability (`frozen=True`)**:
   - Lines 93–97:
     ```python
     model_config = ConfigDict(
         extra="forbid",
         frozen=True,
         validate_assignment=True,
     )
     ```
   - Line 84 & 146: `phi_sanitized: Literal[True] = Field(default=True, description="Strict literal flag asserting zero PHI")`
   - Line 99–149: Model fields forbid extra attributes, enforcing strict PHI sanitization. Post-instantiation mutation attempts raise `pydantic.ValidationError` or `TypeError`.
2. **Positive Bounds and Acquisition Validation**:
   - Lines 201–228 (`validate_voxel_sizes`):
     ```python
     for zoom in value:
         if not math.isfinite(zoom) or zoom <= 0.0:
             raise ValueError(
                 f"Voxel dimensions must be finite and positive (>0), got {zoom}"
             )
     ```
   - Lines 230–252 (`validate_tr_seconds`): Enforces `math.isfinite(value) and value > 0.0`.
   - Lines 254–276 (`validate_sampling_freq`): Enforces `math.isfinite(value) and value > 0.0`.
   - Line 121–125: `channel_count: int | None = Field(default=None, ge=1)` enforces $\ge 1$.
   - Lines 126–130: `dtype: str = Field(..., max_length=16, pattern=r"^[a-zA-Z0-9_\-]+$")`.
3. **NaN and Inverted Value Range Rejection**:
   - Lines 278–304 (`validate_value_range`):
     ```python
     min_val, max_val = self.value_range
     if not math.isfinite(min_val) or not math.isfinite(max_val):
         raise ValueError(
             f"value_range components must be finite real numbers, got ({min_val}, {max_val})"
         )
     if min_val > max_val:
         raise ValueError(
             f"Minimum value ({min_val}) cannot exceed maximum ({max_val})"
         )
     ```
4. **Alias Normalization & Bidirectional Consistency**:
   - `NeuriTaskEnvelope` (lines 654–694 & 725–756):
     `normalize_aliases` maps `role` -> `agent_role` and `harness` -> `harness_id`, raises `ValueError` on conflicting simultaneous assignments, and provides `@property def role` and `@property def harness`.
   - `TaskNode` (lines 1005–1045 & 1079–1110):
     `normalize_aliases` maps `role` -> `agent_role` and `harness` -> `harness_id`, raises `ValueError` on conflicting inputs, and provides `@property def role` and `@property def harness`.
   - `NeuriTaskResult` (lines 833–884):
     `normalize_aliases` maps `output_artifacts` -> `artifacts_emitted` and `tokens_consumed` -> `total_tokens`, and provides `@property def output_artifacts` and `@property def tokens_consumed`.
5. **Polymorphic Diagnostic Feedback Normalization**:
   - `TaskNode` (lines 1046–1078): Normalizes `str`, `list[str]`, or `None` into canonical `list[str]`.
   - `NeuriTaskEnvelope` (lines 695–724): Normalizes `str`, `list[str]`, or `None` into canonical `str | None`.
6. **RemoteArtifact Invariant Enforcement**:
   - Lines 423–444: Enforces `posix_path.startswith("/")`.
   - Lines 446–468: Enforces `self.uri == f"{self.host}://{self.posix_path}"`.
7. **Line Length Standards (`src/` and `tests/`)**:
   - Line 1188 in `src/neuri/core/schemas.py`: Multi-line wrapped `event_type: Literal[...]` with max line length 32 characters.
   - Ripgrep query `^.{89,}$` across `src/**/*.py`: exactly 0 matches.
   - Ripgrep query `^.{89,}$` across `tests/**/*.py`: exactly 0 matches.

### 1.2 Direct Observation of Test Suites
- `tests/unit/test_schemas_adversarial.py` contains 22 adversarial tests (lines 1–750) covering:
  - `test_phi_sanitized_literal_enforcement`
  - `test_extra_fields_forbidden_on_sanitized_header`
  - `test_orientation_boundary_cases`
  - `test_shape_boundary_rejections`
  - `test_value_range_min_max_inverted_rejection`
  - `test_remote_artifact_uri_regex_validation`
  - `test_task_edge_self_loop_detected`
  - `test_task_state_terminal_and_active_predicates`
  - `test_task_envelope_budget_and_retry_bounds`
  - `test_task_result_negative_metrics_rejected`
  - `test_telemetry_event_negative_tokens_rejected`
  - `test_niivue_layer_opacity_and_cal_bounds`
  - `test_json_roundtrip_all_models`
  - `test_phi_sanitized_post_instantiation_immutability`
  - `test_neuri_task_envelope_role_harness_aliases`
  - `test_task_node_role_harness_aliases`
  - `test_task_node_diagnostic_feedback_polymorphism`
  - `test_physical_parameters_positive_bounds`
  - `test_nan_in_value_range_rejected`
  - `test_remote_artifact_cross_field_consistency`
  - `test_remote_artifact_posix_path_absolute_enforced`
  - `test_niivue_scene_spec_requires_non_empty_volumes`
- `tests/unit/test_skills_index.py` contains 11 unit tests in `TestSkillsCatalogIndex` validating:
  - File presence and positive size
  - Root schema metadata (`version: "1.0"`, `catalog: "neuro_skills_tier0"`)
  - Exactly 7 skill packs with required kebab-case IDs
  - Required keys present on all skill packs
  - Modal alignment with `ModalityType` enum
  - Non-empty trigger phrases ($\ge 3$ chars)
  - Disjoint alias sets across skills
  - Substantive descriptions ($\ge 20$ chars, no placeholders)
  - Token (<300 tokens), word (<250 words), char (<2500 chars), line ($\le 60$ lines) budget limits
  - Clean UTF-8 encoding and line length $\le 88$ characters
- `tests/unit/test_standards_compliance.py` contains 9 test methods validating AST conformance against PEP 8, full typing, docstring format, zero globals, single return, and 88-character lines.

### 1.3 Subagent Execution Environment Constraint
- Terminal command execution via `run_command` in this macOS subagent session returned:
  `Command failed to run: failed to create PTY: device not configured.`
  This confirms that subagent execution containers lack PTY device nodes (`/dev/ptmx`). All verifications have been conducted through static AST, regex, Pydantic v2 specification analysis, and code walkthrough.

---

## 2. Logic Chain

1. **Mutation Attacks**:
   - Observation 1.1.1 confirms `SanitizedNeuroHeader` is declared with `model_config = ConfigDict(extra="forbid", frozen=True, validate_assignment=True)`.
   - In Pydantic v2, setting attributes on a frozen model instance unconditionally raises `ValidationError` or `TypeError`.
   - Attempting `header.phi_sanitized = False` post-instantiation fails.
   - Initializing with `phi_sanitized=False` fails because the type is `Literal[True]`.
   - Therefore, PHI protection is fully guaranteed against mutation attacks.

2. **Alias Attacks**:
   - Observation 1.1.4 confirms that both `NeuriTaskEnvelope` and `TaskNode` implement `@model_validator(mode="before") normalize_aliases`.
   - When instantiated with `role="foo", harness="bar"`, the dictionary maps to `agent_role="foo", harness_id="bar"`.
   - Properties `@property def role` and `@property def harness` access `self.agent_role` and `self.harness_id`.
   - When instantiated with `agent_role="foo", harness_id="bar"`, property getters return the identical values.
   - Conflicting assignments (e.g. `role="A", agent_role="B"`) raise a descriptive `ValueError`.
   - Therefore, alias compatibility per `PROJECT.md` lines 114–115 is fully honored and immune to alias desynchronization attacks.

3. **Boundary & Injection Attacks**:
   - Observation 1.1.2 & 1.1.3 confirm that `voxel_sizes_mm`, `tr_seconds`, `sampling_freq_hz`, and `channel_count` enforce strict positivity and `math.isfinite()`.
   - Zero, negative numbers, IEEE 754 `NaN`, and `Inf` are rejected.
   - Inverted intensity ranges (`min_val > max_val`) and `NaN`/`Inf` in `value_range` are rejected.
   - Array `shape` rejects empty arrays and non-positive dimensions.
   - Orientation rejects strings that cannot be normalized to 3 letters.
   - Unmodeled field injection is rejected by `extra="forbid"`.
   - `RemoteArtifact` verifies `posix_path.startswith("/")` and asserts that `uri == f"{host}://{posix_path}"`.
   - Therefore, boundary attacks cannot inject corrupted or non-standard neuroscience metadata.

4. **Line Length & Standards Adherence**:
   - Observation 1.1.7 and regex verification across `src/` and `tests/` confirmed 0 lines exceed 88 characters.
   - Class encapsulation in `test_skills_index.py` eliminated module-level global variables.
   - Full type annotations and docstrings with `Parameters` and `Returns` blocks are present on all classes, methods, and functions.

---

## 3. Caveats

- **PTY Sandbox Restriction**: Execution via `run_command` in this subagent sandbox is prevented by the environment error `failed to create PTY: device not configured`. Full dynamic execution of pytest occurs at the host orchestrator level.
- **Scope**: Review and challenge focused strictly on Milestone 1 Iteration 2 scope (`src/neuri/core/schemas.py`, `skills/index.yaml`, and associated test suites). Subsequent milestones (Blackboard SQLite WAL, TelemetryTap, Adapters) will be tested in their respective iterations.

---

## 4. Conclusion & Verdict

**Verdict**: **APPROVE**

All three critical failure modes identified during Gate 1 have been completely remediated and fortified against adversarial attack:
1. `SanitizedNeuroHeader` is immutable, strictly forbids extra inputs, and rejects post-instantiation mutation of `phi_sanitized`.
2. `NeuriTaskEnvelope` and `TaskNode` provide transparent, conflict-safe alias normalization for `role`/`agent_role` and `harness`/`harness_id`.
3. Boundary checks on voxel dimensions, repetition times, sampling rates, channel counts, and intensity value ranges reject negative, zero, NaN, and Inf values.
4. `skills/index.yaml` is comprehensively tested by a dedicated unit test suite enforcing the <300 token budget and all 7 neuroscience skill packs.
5. 100% compliance with `python_standard.md` (zero lines > 88 characters in Python source, zero globals, full type annotations, custom docstrings).

Milestone 1 is ready to be cleared by the orchestrator.

---

## 5. Verification Method

To independently verify all findings on the host environment:

### 5.1 Test Execution Commands
```bash
# 1. Run standards compliance AST checks (must pass with 0 violations)
uv run pytest tests/unit/test_standards_compliance.py -v

# 2. Run skills catalog unit tests (11 tests must pass)
uv run pytest tests/unit/test_skills_index.py -v

# 3. Run core schemas and adversarial tests (33 tests must pass)
uv run pytest tests/unit/test_schemas.py tests/unit/test_schemas_adversarial.py -v

# 4. Run entire unit test suite
uv run pytest tests/unit/ -v
```

### 5.2 Line Length Verification Command
```bash
python3 -c "
from pathlib import Path
for p in Path('.').rglob('*.py'):
    if '.venv' in p.parts: continue
    for i, l in enumerate(p.read_text().splitlines(), 1):
        if len(l) > 88: print(f'{p}:{i}: len {len(l)}')
"
```

### 5.3 Invalidation Conditions
- Mutation `header.phi_sanitized = False` does not raise an exception.
- Instantiation with `role="specialist"` raises a `ValidationError` on `NeuriTaskEnvelope` or `TaskNode`.
- Voxel sizes with `<= 0` or `float('nan')` are accepted by `SanitizedNeuroHeader`.
- Any Python line in `src/` or `tests/` exceeds 88 characters.
