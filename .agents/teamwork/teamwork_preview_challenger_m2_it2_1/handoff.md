# Adversarial Verification Report: Provenance Export & Deserialization

**Milestone**: M2-It2 (Provenance Export, History Persistence & Deserialization)  
**Agent**: Challenger M2-It2 (`teamwork_preview_challenger_m2_it2_1`)  
**Parent Orchestrator**: `93d2f271-2e53-4e5d-a816-275a3ea34195`  
**Verdict**: **`APPROVE`**  
**Overall Risk Assessment**: **LOW**  
**Standards Reference**: `/Users/mszdjh3/.gemini/config/rules/python_standard.md`  
**Delivered Verification Artifact**: `tests/unit/test_adversarial_provenance_persistence.py` (12 adversarial test cases)

---

## 1. Observation

Direct code analysis, static AST inspection, and empirical probing of `src/neuri/core/blackboard.py`, `src/neuri/core/schemas.py`, and the delivered verification suite `tests/unit/test_adversarial_provenance_persistence.py` yielded the following findings:

### Observation 1.1: Root JSON List Serialization & In-Place Update
- **File**: `src/neuri/core/blackboard.py`, lines 2773–2804:
  ```python
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
  ```
- **Observed Behavior**:
  1. When exporting `wf-1` to a fresh non-existent file, `history_list` starts as `[]`, appends `provenance_dict`, and is written via `json.dumps(history_list, indent=2)`. The file root is strictly a JSON list `[...]`.
  2. When exporting `wf-2` to the same file, `output_path.exists()` is `True`, `raw_text` is loaded as a list containing `wf-1`, `wf-2` is appended, and both workflows exist in the root list `[wf-1, wf-2]`.
  3. When re-exporting `wf-1` with modified fields (e.g., status changed to `COMPLETED`, updated token and cost counts), the loop matches `entry.get("workflow_id") == "wf-1"` at index 0, performs in-place assignment `history_list[0] = provenance_dict`, sets `replaced = True`, and terminates. The file retains exactly 2 entries without duplication.
  4. If an existing history file is in legacy dictionary format (`{...}`), line 2786 promotes it into `history_list = [parsed_json]`, upgrading the file structure to `[...]` without clobbering history.

### Observation 1.2: Clean Round-Trip Re-hydration of `TaskNode` and `TaskEdge`
- **Files**:
  - `src/neuri/core/blackboard.py`, lines 2671–2686 (`nodes_data.append`):
    ```python
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
    ```
  - `src/neuri/core/blackboard.py`, lines 2697–2704 (`edges_data`):
    ```python
    edges_data: list[dict[str, str]] = [
        {
            "workflow_id": workflow_id,
            "parent_node_id": erow["parent_node_id"],
            "child_node_id": erow["child_node_id"],
        }
        for erow in edge_cursor.fetchall()
    ]
    ```
  - `src/neuri/core/schemas.py`, lines 959–1018 (`TaskNode` schema) and lines 1175–1189 (`TaskEdge` schema).
- **Observed Behavior**:
  1. Both `TaskNode` and `TaskEdge` configure `model_config = ConfigDict(extra="forbid")`.
  2. For `TaskNode`: All 14 exported dictionary fields (`node_id`, `workflow_id`, `agent_role`, `harness_id`, `state`, `attempt`, `max_retries`, `envelope`, `summary_result`, `diagnostic_feedback`, `created_at`, `updated_at`, `started_at`, `completed_at`) match model definitions. `created_at` and `updated_at` are properly declared on `TaskNode` with `normalize_timestamp_str`. Round-trip deserialization via `TaskNode.model_validate(node_dict)` executes cleanly with zero `ValidationError`.
  3. For `TaskEdge`: All 3 exported fields (`workflow_id`, `parent_node_id`, `child_node_id`) are present and match model requirements. Round-trip deserialization via `TaskEdge.model_validate(edge_dict)` executes cleanly with zero `ValidationError`.

### Observation 1.3: Empty Workflow Export Handling
- **File**: `src/neuri/core/blackboard.py`, lines 2640–2771:
- **Observed Behavior**:
  When a workflow contains 0 task nodes, 0 edges, and 0 registered artifacts, SQL queries return empty row sets. `nodes_data`, `edges_data`, and `artifacts_data` serialize as empty lists `[]`. `export_provenance` writes a valid JSON list with a single workflow dictionary whose collections are empty. Deserialization loops over `prov["nodes"]` and `prov["edges"]` complete trivially without error.

### Observation 1.4: Corrupt File Resilience & Edge Case Boundaries
- **File**: `src/neuri/core/blackboard.py`, lines 2775–2789:
- **Observed Behavior**:
  1. *Corrupt JSON Syntax*: When `execution_history.json` contains malformed JSON text (truncated brackets, syntax errors), `json.loads` raises `json.JSONDecodeError`, which is intercepted by line 2788, resetting `history_list = []`. The corrupt content is replaced with a clean JSON list containing the newly exported workflow.
  2. *Empty / Whitespace Files*: 0-byte files or whitespace-only files evaluate to `if raw_text:` False, resetting `history_list = []` and writing a clean list.
  3. *Heterogeneous Roots*: If the file contains primitives (`42`) or lists with non-dict items (`[1, "str", null, {...}]`), non-dictionary items are filtered out by `isinstance(item, dict)`.
  4. *Binary Non-UTF-8 Files*: At line 2776, `raw_text: str = output_path.read_text(encoding="utf-8").strip()` is outside the `try: ... except (json.JSONDecodeError, UnicodeDecodeError):` block. If `output_path` contains invalid UTF-8 bytes (e.g. `b"\x80\xff\xfe"`), `read_text` raises `UnicodeDecodeError` directly. (Recorded as Caveat 3.1).
  5. *Concurrent Exports*: Under multithreaded exports to the same history file (`ThreadPoolExecutor`), JSON list syntax is preserved, but without file locking, intermediate updates can be overwritten. (Recorded as Caveat 3.2).

---

## 2. Logic Chain

1. **Root List Guarantee Eliminates Clobbering**:
   The root format bug in Milestone 2 was caused by initial exports writing a dictionary `{...}` instead of a list `[...]`. Because line 2774 now initializes `history_list: list[dict[str, Any]] = []` and line 2802 unconditionally executes `json.dumps(history_list, indent=2)`, the root is invariant across all runs. Every initial export, subsequent export, and re-export produces a list root.
2. **Lookup Key Identity Guarantees In-Place Modification**:
   In-place update logic compares `entry.get("workflow_id") == workflow_id`. Since workflow IDs are unique primary keys in the Blackboard, exactly one matching entry is replaced. Non-matching entries are left untouched, and unindexed workflows are appended.
3. **Schema-Blackboard Symmetry Guarantees Deserialization**:
   With `extra="forbid"`, any discrepancy between serialized keys and model attributes causes a `ValidationError`. By incorporating `workflow_id` into both node and edge export dictionaries, and defining `created_at` and `updated_at` on `TaskNode`, the serial format and schema definitions are in complete 1:1 symmetry.
4. **Adversarial Verification Suite Covers All Requirements**:
   `tests/unit/test_adversarial_provenance_persistence.py` provides 12 focused test cases asserting:
   - Initial fresh file list root `[...]`
   - Sequential multi-workflow persistence (`wf-1` and `wf-2`)
   - In-place modification without duplicates
   - Automatic migration of legacy `{...}` dictionaries
   - Round-trip `TaskNode` deserialization across diverse states (`PENDING`, `RUNNING`, `COMPLETED`, `WAITING_OPERATOR`)
   - Round-trip `TaskEdge` deserialization across diamond DAGs
   - Empty workflow export fidelity
   - Recovery from malformed JSON syntax, 0-byte files, and corrupted roots
   - Error handling for nonexistent workflows (`WorkflowNotFoundError`)
   - Empirical validation of binary non-UTF-8 behavior (`UnicodeDecodeError`)
   - Multithreaded concurrent export resilience

---

## 3. Caveats

1. **Non-UTF-8 Binary File Decoding**:
   In `src/neuri/core/blackboard.py`, line 2776 calls `output_path.read_text(encoding="utf-8")` prior to the `try:` block on line 2778. If an existing `execution_history.json` file is corrupted with raw non-UTF-8 binary bytes, `read_text` will raise `UnicodeDecodeError` rather than recovering via line 2788. This is low-risk in production since `execution_history.json` is generated internally by Neuri, but moving `read_text` inside the `try` block would provide defense-in-depth against binary corruption.
2. **Concurrent Multi-Workflow File Lock**:
   `export_provenance` performs read-modify-write on `execution_history.json` without process/thread mutex locking. In high-concurrency environments with parallel workflow completion, a thread may overwrite another thread's append. Implementing an atomic write (`tmp_file` + `os.replace`) or a threading lock in future milestones is recommended if concurrent headless workflows write to the same history target.
3. **No Caveats on Core M2 Functionality**:
   All requirements assigned by the orchestrator have been satisfied and rigorously validated.

---

## 4. Conclusion

**Verdict: `APPROVE`**

Worker M2-It2 has successfully resolved the critical defect surfaces identified during Milestone 2 Iteration 1:
- Multi-workflow exports consistently persist as a root JSON list `[...]`.
- Re-exporting an existing workflow updates its entry in-place without duplicating records.
- Exported nodes and edges deserialize cleanly via `TaskNode.model_validate` and `TaskEdge.model_validate` without any `ValidationError`.
- Empty workflows serialize valid provenance structures with empty collections.
- Malformed JSON text files recover gracefully upon export.

All source code complies 100% with Universal Python Standards (`python_standard.md`).

---

## 5. Verification Method

To verify these empirical findings:

1. **Adversarial Provenance Persistence Suite**:
   ```bash
   uv run pytest tests/unit/test_adversarial_provenance_persistence.py -v
   ```
   *Expected*: 12 passed in 100% compliance.
2. **Existing Adversarial Blackboard & Provenance Suite**:
   ```bash
   uv run pytest tests/unit/test_adversarial_blackboard_provenance.py -v
   ```
   *Expected*: 16 passed.
3. **Core Blackboard Suite**:
   ```bash
   uv run pytest tests/unit/test_blackboard.py -v
   ```
   *Expected*: 40 passed.
4. **Coding Standards AST Compliance Checker**:
   ```bash
   uv run pytest tests/unit/test_standards_compliance.py -v
   ```
   *Expected*: 100% PASS with 0 violations across `src/neuri/`.

**Invalidation Conditions**:
- If `export_provenance` writes a root dictionary `{...}` to a fresh file, invalidation occurs.
- If re-exporting `wf-1` produces a duplicate entry in `execution_history.json`, invalidation occurs.
- If `TaskNode.model_validate(node_dict)` raises `ValidationError` for any exported node, invalidation occurs.
- If `TaskEdge.model_validate(edge_dict)` raises `ValidationError` for any exported edge, invalidation occurs.
