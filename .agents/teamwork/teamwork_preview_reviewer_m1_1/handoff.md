# Handoff Report: Milestone 1 (M1) Review & Adversarial Stress-Test

**Agent**: `reviewer_m1_1`  
**Roles**: `reviewer`, `critic`  
**Working Directory**: `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_reviewer_m1_1/`  
**Target Milestone**: Milestone 1 (Package Scaffolding, Schemas, Two-Tier Config & Compact Catalog)  
**Date**: 2026-10-25  

---

## Review Summary

**Verdict**: **`REQUEST_CHANGES`**

### Summary of Findings
1. **[Major] Line Length Limit Exceeded (PEP 8 / `python_standard.md` / AST Checker)**: `src/neuri/core/schemas.py:833` is 94 characters long, exceeding the mandatory $\le 88$ character ceiling. This will cause `tests/unit/test_standards_compliance.py` and `ruff check` to fail.
2. **[Major] Interface Contract Discrepancy on `TaskNode` and `NeuriTaskEnvelope`**: In `PROJECT.md` line 114–115, `role: str` and `harness: str` are defined. In `src/neuri/core/schemas.py`, the fields are named `agent_role: str` and `harness_id: str`, and `model_config = ConfigDict(extra="forbid")` is enforced without property aliases or before-validation normalization. Any call to `envelope.role`, `envelope.harness`, `node.role`, `node.harness` or instantiation with `role=`/`harness=` will trigger an unhandled `AttributeError` or `ValidationError`.
3. **[Minor] `TaskNode.diagnostic_feedback` Type Discrepancy**: In `PROJECT.md` line 114, `TaskNode.diagnostic_feedback` is defined as `list[str]`. In `src/neuri/core/schemas.py` line 744, it is typed as `str | None`. Supporting both `list[str] | str | None` prevents type errors across multi-retry runs.
4. **[Minor] Missing Automated Test for `skills/index.yaml`**: While `skills/index.yaml` is valid YAML and strictly $<300$ tokens, there is no unit test file `tests/unit/test_skills_index.py` committed to continuously assert its validity and token budget in CI.

---

## 1. Observation

1. **Line Length in `src/neuri/core/schemas.py` (Line 833)**:
   Inspection of `src/neuri/core/schemas.py` lines 830–835:
   ```python
   830:         Harness identifier.
   831:     timestamp: datetime
   832:         UTC timestamp of event creation. Defaults to current UTC time.
   833:     event_type: Literal["thinking_delta", "token_usage", "tool_lifecycle", "circuit_breaker"]
   834:         Normalized event category.
   835:     thinking_text: str | None
   ```
   Direct character count of line 833:
   `    event_type: Literal["thinking_delta", "token_usage", "tool_lifecycle", "circuit_breaker"]` = 94 characters.
   `python_standard.md` Rule 1 mandates: "strict PEP 8 style guidelines for all Python code (... 79–88 character line limits)."
   `tests/unit/test_standards_compliance.py` line 18 specifies `MAX_LINE_LENGTH: int = 88` and flags any line $>88$ characters.

2. **Interface Contract for `TaskNode` and `NeuriTaskEnvelope` in `PROJECT.md`**:
   `PROJECT.md` lines 114–115 specify:
   ```markdown
   - `TaskNode`: `node_id: str`, `workflow_id: str`, `role: str`, `harness: str`, `state: TaskState`, `envelope: NeuriTaskEnvelope`, `diagnostic_feedback: list[str]`
   - `NeuriTaskEnvelope`: `workflow_id: str`, `node_id: str`, `role: str`, `harness: str`, `task_instruction: str`, `input_artifacts: list[RemoteArtifact]`, `max_tokens_budget: int = 64000`, `max_cost_usd: float = 10.00`, `attempt_number: int = 1`, `max_retries: int = 2`
   ```
   In `src/neuri/core/schemas.py`:
   - `NeuriTaskEnvelope` (lines 451, 455):
     `agent_role: str = Field(...)`
     `harness_id: str = Field(...)`
     Neither property aliases (`role`, `harness`) nor `model_validator(mode="before")` alias normalization exist.
   - `TaskNode` (lines 714, 718):
     `agent_role: str = Field(...)`
     `harness_id: str = Field(...)`
     Neither property aliases (`role`, `harness`) nor `model_validator(mode="before")` alias normalization exist.
   - Both models enforce `model_config = ConfigDict(extra="forbid")`.

3. **Compact Catalog `skills/index.yaml` Token Count**:
   File `skills/index.yaml` has 52 lines, 142 words, and 1961 raw bytes.
   All 7 required neuroscience skill packs (`bids-standard`, `neuroimaging-preproc`, `fmri-postproc`, `dwi-tractography`, `eeg-meg-pipeline`, `remote-compute-slurm`, `scientific-writing-neuro`) are present.
   Word count: 142 words $\approx$ 185–220 tokens in standard BPE tokenizers (`cl100k_base` / `o200k_base`), well within the $<300$ token ceiling.

4. **SanitizedNeuroHeader PHI Enforcement**:
   In `src/neuri/core/schemas.py` lines 135–138:
   `phi_sanitized: Literal[True] = Field(default=True, description="Strict literal flag asserting zero PHI")`
   Together with `model_config = ConfigDict(extra="forbid")`, passing `phi_sanitized=False` or passing any extra patient identifier fields raises `pydantic.ValidationError`.

5. **Two-Tier Configuration and Workspace Initializer**:
   `src/neuri/core/config.py` correctly implements:
   - `deep_merge` for recursive dictionary inheritance.
   - `ConfigManager.load()` reading `~/.neuri/config.toml` merged with `.neuri/neuri.toml`.
   - `ConfigManager.init_project_workspace()` creating `neuri.toml`, `state.db` (in SQLite WAL mode via PRAGMA statements), `references.bib`, `execution_history.json`, `qa_snapshots/`, and `skills/`.
   - `model_dump(mode="python", exclude_none=True)` in `save_project_config()`, safely preventing TOML `None` serialization failures.

6. **Subshell PTY Execution Constraint**:
   Executing commands via terminal tool confirmed:
   `Command failed to run: failed to create PTY: device not configured.`
   As a result, dynamic subprocess tests cannot be invoked within this subagent container; all code evaluation was conducted via rigorous AST, regex, and static inspection.

---

## 2. Logic Chain

1. **Line Length Failure**:
   - `python_standard.md` Rule 1 mandates 79–88 character limits without exceptions.
   - Observation 1 confirmed line 833 of `src/neuri/core/schemas.py` contains 94 characters.
   - `tests/unit/test_standards_compliance.py` will flag this line as a failure when executed in CI or M7.
   - Therefore, `src/neuri/core/schemas.py` must be formatted to ensure all lines are $\le 88$ characters.

2. **Downstream API Compatibility on Task Contracts**:
   - Observation 2 revealed that while `NeuriTaskResult` correctly accommodated alias properties (`output_artifacts` and `tokens_consumed`) matching `PROJECT.md` line 116, `NeuriTaskEnvelope` and `TaskNode` did not implement aliases for `role` and `harness`.
   - Because `extra="forbid"` is active on both models, downstream modules (M2 Blackboard, M4 Adapters, M5 Orchestrator) adhering to the `PROJECT.md` interface specifications will fail on instantiation if they pass `role` or `harness`, or will fail on attribute access (`node.role`, `envelope.harness`).
   - Providing `@property` aliases and `@model_validator(mode="before")` on both `NeuriTaskEnvelope` and `TaskNode` will ensure seamless contract conformance.

3. **Integrity Assessment**:
   - Actively checked for hardcoded test bypasses, facade implementations, and fabricated claims.
   - Source code implements genuine Pydantic models, real regex validation, real SQLite WAL connection and pragma execution, and genuine TOML parsing.
   - No integrity violations were found.

---

## 3. Caveats

1. **PTY Sandbox Constraint**: Subprocess execution could not be spawned from this subagent turn due to `failed to create PTY: device not configured`. All verifications were performed via static AST analysis, regex pattern matching, and file structure examination.
2. **Backward-Compatible Subclass Pattern**: In `src/neuri/core/config.py`, alias classes (`ProjectConfig(WorkspaceConfig)`, etc.) were used to avoid module-level assignments that could trigger AST global-variable detectors. This pattern is compliant with `python_standard.md`.

---

## 4. Conclusion & Actionable Next Steps

The Milestone 1 implementation is genuine and well-architected, but requires straightforward modifications before final approval.

### Required Changes for `worker_m1`:
1. **Fix Line 833 in `src/neuri/core/schemas.py`**:
   Reformat the docstring of `TelemetryEvent` so that line 833 is split across lines and remains $\le 88$ characters.
2. **Add `role` and `harness` Aliases to `NeuriTaskEnvelope` and `TaskNode`**:
   In `src/neuri/core/schemas.py`:
   - Add `@property def role(self) -> str: return self.agent_role`
   - Add `@property def harness(self) -> str: return self.harness_id`
   - Add `@model_validator(mode="before")` on both models to accept `role` and `harness` interchangeably with `agent_role` and `harness_id`.
3. **Harmonize `TaskNode.diagnostic_feedback`**:
   Update `TaskNode.diagnostic_feedback` to accept `list[str] | str | None` to eliminate friction with `PROJECT.md` line 114.
4. **Add `tests/unit/test_skills_index.py`**:
   Create a dedicated unit test asserting `skills/index.yaml` exists, parses as valid YAML, contains all 7 skill packs, and remains strictly $<300$ tokens.

---

## 5. Verification Method

Once the fixes are applied by `worker_m1`, verify via:

1. **AST & Standards Compliance**:
   ```bash
   uv run pytest tests/unit/test_standards_compliance.py -v
   uv run ruff check src/ tests/
   ```
   *Expected*: 0 violations; line 833 of `schemas.py` no longer flagged.

2. **Interface Alias Verification**:
   ```python
   from neuri.core.schemas import NeuriTaskEnvelope, TaskNode, TaskState

   env = NeuriTaskEnvelope(
       workflow_id="wf-1",
       node_id="n-1",
       role="neuroimaging_specialist",
       harness="agy",
       system_prompt="sys",
       task_instruction="inst",
   )
   assert env.role == "neuroimaging_specialist"
   assert env.harness == "agy"
   assert env.agent_role == "neuroimaging_specialist"
   assert env.harness_id == "agy"

   node = TaskNode(
       node_id="n-1",
       workflow_id="wf-1",
       role="neuroimaging_specialist",
       harness="agy",
   )
   assert node.role == "neuroimaging_specialist"
   assert node.harness == "agy"
   ```

3. **Skills Catalog Validation**:
   ```bash
   uv run pytest tests/unit/test_skills_index.py -v
   ```

*Invalidation Conditions*:
- Any line in `src/` or `tests/` exceeding 88 characters.
- Failure of `TaskNode` or `NeuriTaskEnvelope` to accept `role` or `harness`.
- `skills/index.yaml` exceeding 300 tokens.
