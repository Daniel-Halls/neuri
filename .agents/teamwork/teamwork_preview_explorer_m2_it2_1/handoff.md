# Investigation Report & Drop-In Fix Strategy: M2 Provenance Export & Schema Re-hydration

**Target Files**:
- `src/neuri/core/blackboard.py` (lines 2573–2705, 2748–2762)
- `src/neuri/core/schemas.py` (lines 940–1080)
- `tests/unit/test_blackboard.py` (lines 1725–1730)

**Target Issues**: Challenger M2-2 Observations 1.1, 1.2, 1.3  
**Investigator**: Explorer M2-It2 Provenance (`teamwork_preview_explorer_m2_it2_1`)  
**Date**: 2026-10-25  

---

## 1. Observation

Direct code and AST inspection of `src/neuri/core/blackboard.py`, `src/neuri/core/schemas.py`, and test suites `tests/unit/test_adversarial_blackboard_provenance.py` and `tests/unit/test_blackboard.py` revealed three interrelated structural defects:

### 1.1 Multi-Workflow History Clobbering / Provenance File Root Structure
In `src/neuri/core/blackboard.py` lines 2673–2705:
```python
output_path.parent.mkdir(parents=True, exist_ok=True)
if output_path.exists():
    raw_text: str = output_path.read_text(encoding="utf-8").strip()
    if raw_text.startswith("["):
        try:
            history_list: list[Any] = json.loads(raw_text)
            if not isinstance(history_list, list):
                history_list = []
        except json.JSONDecodeError:
            history_list = []

        replaced: bool = False
        for idx, entry in enumerate(history_list):
            if (
                isinstance(entry, dict)
                and entry.get("workflow_id") == workflow_id
            ):
                history_list[idx] = provenance_dict
                replaced = True
                break
        if not replaced:
            history_list.append(provenance_dict)

        output_path.write_text(
            json.dumps(history_list, indent=2), encoding="utf-8"
        )
        return provenance_dict

output_path.write_text(
    json.dumps(provenance_dict, indent=2), encoding="utf-8"
)
return provenance_dict
```
- **Observed Behavior**:
  1. When `export_provenance` is called on a file that does not yet exist, line 2701 executes: `output_path.write_text(json.dumps(provenance_dict, indent=2), encoding="utf-8")`. This persists a JSON Object (`{...}`) at the root, NOT a JSON list (`[...]`).
  2. When a second workflow (e.g. `wf-run-2`) is exported to the same path, `output_path.exists()` is `True`, but `raw_text.startswith("[")` is `False` because the existing file begins with `{`.
  3. Consequently, the list merge logic (lines 2676–2699) is completely bypassed. Line 2701 executes again and overwrites `output_path`.
  4. The previous workflow's provenance record is permanently clobbered.
  5. As verified in `TestAdversarialProvenanceExport.test_export_provenance_multi_workflow_clobber_vulnerability`, exporting `wf-run-1` followed by `wf-run-2` leaves only `wf-run-2` on disk.

### 1.2 Pydantic Re-hydration Failure on Exported `nodes`
In `src/neuri/core/blackboard.py` lines 2573–2587 vs `src/neuri/core/schemas.py` lines 952–1004:
- In `blackboard.py`:
  ```python
  nodes_data.append({
      "node_id": nrow["node_id"],
      "agent_role": nrow["agent_role"],
      "harness_id": nrow["harness_id"],
      "state": nrow["state"],
      "attempt": nrow["attempt"],
      "max_retries": nrow["max_retries"],
      "envelope": envelope_obj,
      "summary_result": nrow["summary_result"],
      "diagnostic_feedback": feedback_list,
      "created_at": nrow["created_at"],
      "updated_at": nrow["updated_at"],
      "started_at": nrow["started_at"],
      "completed_at": nrow["completed_at"],
  })
  ```
- In `schemas.py`:
  ```python
  class TaskNode(BaseModel):
      model_config = ConfigDict(extra="forbid")
      node_id: str = Field(...)
      workflow_id: str = Field(...)
      agent_role: str = Field(...)
      harness_id: str = Field(...)
      state: TaskState = Field(default=TaskState.PENDING)
      ...
      started_at: datetime | None = Field(default=None)
      completed_at: datetime | None = Field(default=None)
  ```
- **Observed Behavior**:
  1. `workflow_id` is a required field on `TaskNode`. However, `nodes_data.append` omits `"workflow_id": workflow_id`.
  2. `created_at` and `updated_at` are serialized into each node dict, but `TaskNode` does not define either field and enforces `model_config = ConfigDict(extra="forbid")`.
  3. Attempting to deserialize an exported node dict via `TaskNode.model_validate(node_dict)` crashes immediately with `ValidationError`:
     - `workflow_id: Field required [type=missing]`
     - `created_at: Extra inputs are not permitted [type=extra_forbidden]`
     - `updated_at: Extra inputs are not permitted [type=extra_forbidden]`

### 1.3 Pydantic Re-hydration Failure on Exported `edges`
In `src/neuri/core/blackboard.py` lines 2598–2604 vs `src/neuri/core/schemas.py` lines 1134–1148:
- In `blackboard.py`:
  ```python
  edges_data: list[dict[str, str]] = [
      {
          "parent_node_id": erow["parent_node_id"],
          "child_node_id": erow["child_node_id"],
      }
      for erow in edge_cursor.fetchall()
  ]
  ```
- In `schemas.py`:
  ```python
  class TaskEdge(BaseModel):
      model_config = ConfigDict(extra="forbid")
      workflow_id: str = Field(...)
      parent_node_id: str = Field(...)
      child_node_id: str = Field(...)
  ```
- **Observed Behavior**:
  1. `workflow_id` is required on `TaskEdge`.
  2. `edges_data` omits `workflow_id`.
  3. Calling `TaskEdge.model_validate(edge_dict)` crashes immediately with `ValidationError: workflow_id: Field required [type=missing]`.

### 1.4 Downstream Unit Test Assumption in `test_blackboard.py`
In `tests/unit/test_blackboard.py` lines 1725–1729:
```python
assert export_file.is_file()
loaded: dict[str, Any] = json.loads(
    export_file.read_text(encoding="utf-8")
)
assert loaded["workflow_id"] == "wf-prov"
```
- **Observed Behavior**:
  When `test_export_provenance_full_workflow` was written, it tested against the buggy `export_provenance` that created a JSON object root `{...}` on initial file creation. When `export_provenance` is corrected to always maintain a JSON list root `[...]`, `json.loads(...)` will return a list. Line 1729 (`loaded["workflow_id"]`) will fail with `TypeError: list indices must be integers or slices, not str` unless updated.

---

## 2. Logic Chain

1. **Premise 1 (Immutable Multi-Workflow History)**:
   In `ORIGINAL_REQUEST.md` (R2) and `PROJECT.md` line 7, Neuri specifies provenance logging to `.neuri/execution_history.json`. In `config.py` (lines 466–468) and `test_config.py` (line 466), workspace initialization guarantees that `execution_history.json` starts as a JSON list `[]`. The public docstring for `Blackboard.export_provenance` states: "Safely merges into existing execution_history.json lists."
2. **Step 2 (Root List Invariance)**:
   Per Observation 1.1, if `export_provenance` creates a file directly with a single dict, it breaks the list root invariant. Any subsequent export fails to recognize the file as a list and overwrites it. Therefore:
   - Whether `output_path` exists or not, `export_provenance` MUST ensure the file root is always serialized as `[...]`.
   - If an existing file contains a legacy Object `{...}`, it must be gracefully parsed and promoted into a list `[existing_dict]`.
   - If `workflow_id` matches an existing entry, that entry must be updated in place (idempotency); if not, it must be appended.
   - The method must still return `provenance_dict` (type `dict[str, Any]`), conforming to `PROJECT.md` interface contract `Blackboard.export_provenance(workflow_id: str, output_path: Path) -> dict[str, Any]`.
3. **Step 3 (Schema Alignment for Nodes and Edges)**:
   Per Observations 1.2 and 1.3, exported dictionary keys must match the required schema models `TaskNode` and `TaskEdge` when callers re-hydrate them with `TaskNode.model_validate(node_dict)` and `TaskEdge.model_validate(edge_dict)`.
   - Both `TaskNode` and `TaskEdge` enforce `model_config = ConfigDict(extra="forbid")`.
   - Adding `"workflow_id": workflow_id` to both `nodes_data.append` and `edges_data` resolves the `type=missing` error for both models.
4. **Step 4 (Resolution of Node Timestamps: `created_at` / `updated_at`)**:
   We analyzed two architectural choices for `created_at` and `updated_at`:
   - *Option A: Strip `created_at` and `updated_at` from `export_provenance`*:
     While this avoids modifying `TaskNode`, it permanently discards task node creation and modification timestamps from `execution_history.json`. In scientific workflow pipelines, auditability and performance profiling require knowing when each DAG node was queued and modified.
   - *Option B: Add `created_at` and `updated_at` to `TaskNode` with `default=None` and an ISO string normalizer*:
     Adding `created_at: str | None = None` and `updated_at: str | None = None` to `TaskNode` aligns the domain model with the SQLite table schema (`created_at TEXT NOT NULL, updated_at TEXT NOT NULL`), allows `_row_to_task_node` to preserve timestamps upon retrieval, preserves full timing fidelity in `execution_history.json`, and allows seamless Pydantic re-hydration.
   - *Decision*: Option B is strictly superior. It satisfies all constraints and enhances domain integrity.

---

## 3. Caveats

- **No Caveats on Implementation Feasibility**: The changes are purely additive and backward-compatible.
- **PTY Device Allocation Limitation**: As noted by Challenger M2-2, interactive PTY allocation is unavailable in this environment session; verification relies on non-interactive pytest invocations and AST inspections.
- **Unit Test Sync Required**: As documented in Observation 1.4, `tests/unit/test_blackboard.py` line 1729 must be synchronized to inspect `loaded_history[0]["workflow_id"]` instead of indexing the list with a string.

---

## 4. Conclusion & Drop-In Code Strategy

To resolve Observations 1.1, 1.2, and 1.3 cleanly and conform 100% to Universal Python Standards, the following exact drop-in edits are designed for the worker agent (`worker_m2`).

### 4.1 Update `src/neuri/core/schemas.py` (`TaskNode`)

In `src/neuri/core/schemas.py`:
1. In `TaskNode` docstring `Parameters` section (around lines 940–945), document `created_at` and `updated_at`:
```python
    created_at: str | None
        Creation timestamp in ISO 8601 UTC format. Defaults to None.
    updated_at: str | None
        Last update timestamp in ISO 8601 UTC format. Defaults to None.
```
2. In `TaskNode` field declarations (around lines 1000–1005), add:
```python
    created_at: str | None = Field(
        default=None,
        description="Creation timestamp in ISO 8601 UTC format",
    )
    updated_at: str | None = Field(
        default=None,
        description="Last update timestamp in ISO 8601 UTC format",
    )
```
3. In `TaskNode` validators (around lines 1045–1050), add:
```python
    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def normalize_timestamp_str(cls, value: Any) -> str | None:
        """Normalize timestamp input to ISO 8601 formatted string.

        Parameters
        ------------
        value: Any
            Input timestamp value as string, datetime, or None.

        Returns
        --------
            str | None: string or None
                Harmonized ISO 8601 string or None if unassigned.
        """
        result: str | None = None
        if value is None:
            return result
        if isinstance(value, datetime):
            result = value.isoformat()
            return result
        str_val: str = str(value).strip()
        if str_val:
            result = str_val
        return result
```

---

### 4.2 Update `src/neuri/core/blackboard.py` (`export_provenance`)

In `src/neuri/core/blackboard.py`:
1. **Include `workflow_id` in `nodes_data`** (lines 2573–2587):
```python
<<<<
                nodes_data.append({
                    "node_id": nrow["node_id"],
                    "agent_role": nrow["agent_role"],
                    "harness_id": nrow["harness_id"],
                    "state": nrow["state"],
                    "attempt": nrow["attempt"],
                    "max_retries": nrow["max_retries"],
                    "envelope": envelope_obj,
                    "summary_result": nrow["summary_result"],
                    "diagnostic_feedback": feedback_list,
                    "created_at": nrow["created_at"],
                    "updated_at": nrow["updated_at"],
                    "started_at": nrow["started_at"],
                    "completed_at": nrow["completed_at"],
                })
====
                nodes_data.append({
                    "node_id": nrow["node_id"],
                    "workflow_id": workflow_id,
                    "agent_role": nrow["agent_role"],
                    "harness_id": nrow["harness_id"],
                    "state": nrow["state"],
                    "attempt": nrow["attempt"],
                    "max_retries": nrow["max_retries"],
                    "envelope": envelope_obj,
                    "summary_result": nrow["summary_result"],
                    "diagnostic_feedback": feedback_list,
                    "created_at": nrow["created_at"],
                    "updated_at": nrow["updated_at"],
                    "started_at": nrow["started_at"],
                    "completed_at": nrow["completed_at"],
                })
>>>>
```

2. **Include `workflow_id` in `edges_data`** (lines 2598–2604):
```python
<<<<
            edges_data: list[dict[str, str]] = [
                {
                    "parent_node_id": erow["parent_node_id"],
                    "child_node_id": erow["child_node_id"],
                }
                for erow in edge_cursor.fetchall()
            ]
====
            edges_data: list[dict[str, str]] = [
                {
                    "workflow_id": workflow_id,
                    "parent_node_id": erow["parent_node_id"],
                    "child_node_id": erow["child_node_id"],
                }
                for erow in edge_cursor.fetchall()
            ]
>>>>
```

3. **Replace history file persistence and merge logic** (lines 2673–2705):
```python
<<<<
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists():
            raw_text: str = output_path.read_text(encoding="utf-8").strip()
            if raw_text.startswith("["):
                try:
                    history_list: list[Any] = json.loads(raw_text)
                    if not isinstance(history_list, list):
                        history_list = []
                except json.JSONDecodeError:
                    history_list = []

                replaced: bool = False
                for idx, entry in enumerate(history_list):
                    if (
                        isinstance(entry, dict)
                        and entry.get("workflow_id") == workflow_id
                    ):
                        history_list[idx] = provenance_dict
                        replaced = True
                        break
                if not replaced:
                    history_list.append(provenance_dict)

                output_path.write_text(
                    json.dumps(history_list, indent=2), encoding="utf-8"
                )
                return provenance_dict

        output_path.write_text(
            json.dumps(provenance_dict, indent=2), encoding="utf-8"
        )
        return provenance_dict
====
        output_path.parent.mkdir(parents=True, exist_ok=True)
        history_list: list[dict[str, Any]] = []
        if output_path.exists():
            raw_text: str = output_path.read_text(encoding="utf-8").strip()
            if raw_text:
                try:
                    parsed_json: Any = json.loads(raw_text)
                    if isinstance(parsed_json, list):
                        history_list = [
                            item
                            for item in parsed_json
                            if isinstance(item, dict)
                        ]
                    elif isinstance(parsed_json, dict):
                        history_list = [parsed_json]
                except (json.JSONDecodeError, UnicodeDecodeError):
                    history_list = []

        replaced: bool = False
        for idx, entry in enumerate(history_list):
            if entry.get("workflow_id") == workflow_id:
                history_list[idx] = provenance_dict
                replaced = True
                break

        if not replaced:
            history_list.append(provenance_dict)

        output_path.write_text(
            json.dumps(history_list, indent=2), encoding="utf-8"
        )
        return provenance_dict
>>>>
```

4. **Populate timestamps in `_row_to_task_node`** (lines 2748–2761):
```python
<<<<
        node: TaskNode = TaskNode(
            node_id=row["node_id"],
            workflow_id=row["workflow_id"],
            agent_role=row["agent_role"],
            harness_id=row["harness_id"],
            state=TaskState(row["state"]),
            attempt=row["attempt"],
            max_retries=row["max_retries"],
            envelope=envelope_val,
            summary_result=row["summary_result"],
            diagnostic_feedback=feedback_val,
            started_at=started_dt,
            completed_at=completed_dt,
        )
====
        node: TaskNode = TaskNode(
            node_id=row["node_id"],
            workflow_id=row["workflow_id"],
            agent_role=row["agent_role"],
            harness_id=row["harness_id"],
            state=TaskState(row["state"]),
            attempt=row["attempt"],
            max_retries=row["max_retries"],
            envelope=envelope_val,
            summary_result=row["summary_result"],
            diagnostic_feedback=feedback_val,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            started_at=started_dt,
            completed_at=completed_dt,
        )
>>>>
```

---

### 4.3 Update `tests/unit/test_blackboard.py` (`test_export_provenance_full_workflow`)

In `tests/unit/test_blackboard.py` lines 1725–1730:
```python
<<<<
        assert export_file.is_file()
        loaded: dict[str, Any] = json.loads(
            export_file.read_text(encoding="utf-8")
        )
        assert loaded["workflow_id"] == "wf-prov"
====
        assert export_file.is_file()
        loaded_history: list[dict[str, Any]] = json.loads(
            export_file.read_text(encoding="utf-8")
        )
        assert isinstance(loaded_history, list)
        assert len(loaded_history) == 1
        assert loaded_history[0]["workflow_id"] == "wf-prov"
>>>>
```

---

## 5. Verification Method

Once implemented by `worker_m2`, the fixes can be verified with:

1. **Adversarial Provenance Suite**:
   ```bash
   uv run pytest -v tests/unit/test_adversarial_blackboard_provenance.py -k "test_export_provenance"
   ```
   **Expected**:
   - `test_export_provenance_multi_workflow_clobber_vulnerability` PASSES.
   - `test_export_provenance_round_trip_task_node_rehydration` PASSES.
   - `test_export_provenance_round_trip_task_edge_rehydration` PASSES.
   - `test_export_provenance_round_trip_remote_artifact_rehydration` PASSES.
   - `test_export_provenance_unwriteable_directory_raises_permission_error` PASSES.
   - `test_export_provenance_concurrent_exports_do_not_corrupt_json` PASSES.

2. **Standard Blackboard Unit Suite**:
   ```bash
   uv run pytest -v tests/unit/test_blackboard.py
   ```
   **Expected**: 100% pass across all 40 blackboard unit tests.

3. **Schema Unit Suite**:
   ```bash
   uv run pytest -v tests/unit/test_schemas.py
   ```
   **Expected**: 100% pass across all schema validation tests.

4. **AST Standards Verification**:
   Verify PEP 8 compliance, single return type, docstring formatting, and 0 global variables on `src/neuri/core/blackboard.py` and `src/neuri/core/schemas.py`.

5. **Invalidation Conditions**:
   - If `execution_history.json` on disk ever starts with `{` on initial creation, invalidation occurs.
   - If exporting a second workflow causes the first workflow to disappear from `execution_history.json`, invalidation occurs.
   - If `TaskNode.model_validate(data["nodes"][0])` raises `ValidationError`, invalidation occurs.
   - If `TaskEdge.model_validate(data["edges"][0])` raises `ValidationError`, invalidation occurs.
