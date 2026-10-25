# Investigation & Fix Strategy Report: Artifact Registration Security & Integrity

**Agent**: Explorer M2-It2 Artifacts (`teamwork_preview_explorer_m2_it2_2`)  
**Milestone**: M2-It2  
**Scope**: Challenger M2-2 Observations 1.6 & 1.7 (`src/neuri/core/blackboard.py`, `src/neuri/core/schemas.py`)  
**Standards Reference**: `/Users/mszdjh3/.gemini/config/rules/python_standard.md`  

---

## 1. Observation

Direct code and AST inspection of `src/neuri/core/blackboard.py`, `src/neuri/core/schemas.py`, and `tests/unit/test_adversarial_blackboard_provenance.py` revealed the following concrete vulnerabilities:

### Observation 1.1 (Challenger Obs 1.7): Cross-Workflow Node Association Leak
- **Location**: `src/neuri/core/blackboard.py`, lines 1917–1928:
  ```python
  target_node_id: str | None = node_id or artifact.created_by_node
  if target_node_id is not None:
      node_cursor: sqlite3.Cursor = conn.execute(
          "SELECT 1 FROM task_nodes WHERE node_id = ?;",
          (target_node_id,),
      )
      if node_cursor.fetchone() is None:
          raise NodeNotFoundError(
              f"Cannot register artifact: Node '{target_node_id}' "
              "does not exist."
          )
  ```
- **Finding**: The SQL query validates that `target_node_id` exists anywhere in the global `task_nodes` table, but omits the workflow filter `AND workflow_id = ?`.
- **Impact**: An artifact registered under `wf-b` can be bound to a node belonging exclusively to `wf-a`. When `export_provenance("wf-b", ...)` executes, `artifacts` contains references to nodes that do not exist within `wf-b`'s `nodes` list, corrupting provenance graph integrity.
- **Empirical Probe**: Confirmed by `TestAdversarialArtifactRegistration.test_artifact_cross_workflow_node_foreign_key_behavior` in `tests/unit/test_adversarial_blackboard_provenance.py` lines 243–290, which succeeded in attaching an artifact under `wf-b` to a node from `wf-a`.

### Observation 1.2 (Challenger Obs 1.6): Missing SHA-256 Format Validation
- **Location 1**: `src/neuri/core/schemas.py`, lines 377–380:
  ```python
  sha256_header: str = Field(
      ...,
      description="SHA-256 hash of the header metadata",
  )
  ```
- **Location 2**: `src/neuri/core/blackboard.py`, line 327:
  ```sql
  sha256 TEXT NOT NULL,
  ```
- **Finding**: Neither Pydantic schema nor SQLite DDL nor `register_artifact` validates that `sha256_header` is a 64-character lowercase hexadecimal string (`^[0-9a-f]{64}$`). Arbitrary strings (e.g. `"not_a_valid_hex_hash_12345"`) or non-hash data are persisted silently into `.neuri/state.db`.
- **Empirical Probe**: Confirmed by `TestAdversarialArtifactRegistration.test_artifact_malformed_sha256_hash_accepted_silently` lines 291–331.
- **Collateral Test Discovery**: The existing test suite contains 4 locations where 16-character dummy strings were used for `sha256_header`:
  1. `tests/conftest.py`, line 83: `sha256_header="abcdef1234567890"`
  2. `tests/unit/test_schemas.py`, line 175: `sha256_header="a1b2c3d4e5f67890"`
  3. `tests/unit/test_schemas.py`, line 210: `sha256_header="e3b0c44298fc1c14"`
  4. `tests/unit/test_schemas_adversarial.py`, line 418: `sha256_header="0123456789abcdef"`
  Enforcing `pattern=r'^[0-9a-f]{64}$'` in `RemoteArtifact` will fail these 4 tests unless they are expanded to valid 64-character hex strings (e.g. `hash * 4`).

### Observation 1.3: Unwrapped Database `IntegrityError` Leaks
- **Location**: `src/neuri/core/blackboard.py`, lines 1933–1956:
  ```python
  conn.execute(
      """
      INSERT INTO remote_artifacts (
          artifact_id, uri, workflow_id, node_id, host,
          posix_path, modality, space, size_bytes, sha256,
          header_json, bids_entities_json, created_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
      """,
      (...),
  )
  ```
- **Finding**: While `uri` and `(host, posix_path)` have proactive existence checks, `artifact_id` primary key uniqueness is not proactively checked, and `conn.execute(...)` is not wrapped in `try ... except sqlite3.IntegrityError:`.
- **Impact**: Duplicate `artifact_id`, concurrent race conditions, or foreign key constraint violations leak raw `sqlite3.IntegrityError` rather than raising domain `ArtifactRegistrationError` (subclass of `BlackboardError`).
- **Empirical Probe**: Addressed in `test_artifact_duplicate_artifact_id_raises_integrity_error` lines 193–242.

---

## 2. Logic Chain

1. **Intra-Workflow Integrity**:
   - `TaskNode` entities are partitioned by `workflow_id` (compound primary/foreign key semantics).
   - In `export_provenance`, nodes and artifacts are both scoped to `workflow_id`:
     `SELECT ... FROM task_nodes WHERE workflow_id = ?`
     `SELECT ... FROM remote_artifacts WHERE workflow_id = ?`
   - If an artifact's `created_by_node` belongs to another workflow, the exported provenance document has broken referential integrity.
   - Enforcing `SELECT 1 FROM task_nodes WHERE node_id = ? AND workflow_id = ?;` guarantees referential integrity at registration time and raises `NodeNotFoundError` if violated.

2. **Defense-in-Depth SHA-256 Validation**:
   - Validating SHA-256 at the schema level (`RemoteArtifact`) stops malformed data at the application boundary before any processing.
   - Validating at the engine level (`register_artifact`) protects against bypasses (e.g. `model_construct()`).
   - Validating at the database level (`CHECK (length(sha256) == 64 AND NOT (sha256 GLOB '*[^0-9a-f]*'))`) provides absolute storage-level enforcement in standard portable SQLite syntax without external C extensions.

3. **Exception Contract Encapsulation**:
   - The blackboard interface contract must not expose driver-level database exceptions (`sqlite3.IntegrityError`).
   - `ArtifactRegistrationError` inherits from `BlackboardError`.
   - Adding proactive checking of `artifact_id` gives specific error context; wrapping `conn.execute(...)` in `try ... except sqlite3.IntegrityError as exc: raise ArtifactRegistrationError(...) from exc` ensures complete encapsulation.

---

## 3. Caveats

- **PTY Device Allocation Limitation**: `run_command` in this headless terminal environment encounters `failed to create PTY: device not configured.` Execution and validation rely on static analysis, AST compliance, and drop-in code fidelity.
- **Fixture Expansion Required**: Adding `pattern=r"^[0-9a-f]{64}$"` to `RemoteArtifact` requires updating 4 existing test fixtures that used 16-character dummy strings (`tests/conftest.py`, `tests/unit/test_schemas.py`, `tests/unit/test_schemas_adversarial.py`). Exact update snippets are provided below.
- **Adversarial Test Alignment**: The two adversarial tests in `tests/unit/test_adversarial_blackboard_provenance.py` (`test_artifact_cross_workflow_node_foreign_key_behavior` and `test_artifact_malformed_sha256_hash_accepted_silently`) were initially written to prove the bug exists. Once the fix is applied, they must assert `pytest.raises(NodeNotFoundError)` and `pytest.raises(ValidationError)` respectively.

---

## 4. Conclusion & Drop-In Code Proposals

All code proposals strictly adhere to **Universal Python Standards** (`python_standard.md`):
- Strict PEP 8 styling (snake_case, PascalCase, 4-space indent, <= 88 char limit).
- Full type annotations on all parameters and return values.
- Preferred docstring format with `Parameters` (`------------`) and `Returns` (`--------`).
- Zero global variables.

### Patch 1: `src/neuri/core/schemas.py`
Enforce `pattern=r"^[0-9a-f]{64}$"` on `RemoteArtifact.sha256_header`.

```python
<<<<
    sha256_header: str = Field(
        ...,
        description="SHA-256 hash of the header metadata",
    )
====
    sha256_header: str = Field(
        ...,
        pattern=r"^[0-9a-f]{64}$",
        description=(
            "SHA-256 lowercase hexadecimal hash digest of header metadata"
        ),
    )
>>>>
```

### Patch 2: `src/neuri/core/blackboard.py` — DDL & Imports
1. Add `import re` to standard library imports in `src/neuri/core/blackboard.py`:

```python
<<<<
from pathlib import Path
import sqlite3
from typing import Any
====
from pathlib import Path
import re
import sqlite3
from typing import Any
>>>>
```

2. Add SQLite CHECK constraint to `BlackboardSchema.CREATE_REMOTE_ARTIFACTS_TABLE`:

```python
<<<<
        size_bytes INTEGER NOT NULL DEFAULT 0 CHECK (size_bytes >= 0),
        sha256 TEXT NOT NULL,
        header_json TEXT NOT NULL,
====
        size_bytes INTEGER NOT NULL DEFAULT 0 CHECK (size_bytes >= 0),
        sha256 TEXT NOT NULL CHECK (
            length(sha256) == 64 AND NOT (sha256 GLOB '*[^0-9a-f]*')
        ),
        header_json TEXT NOT NULL,
>>>>
```

### Patch 3: `src/neuri/core/blackboard.py` — `register_artifact` Implementation
Replace lines 1860–1957 in `src/neuri/core/blackboard.py` with this drop-in method:

```python
    def register_artifact(
        self,
        artifact: RemoteArtifact,
        workflow_id: str,
        node_id: str | None = None,
    ) -> None:
        """Register a remote artifact in the blackboard provenance store.

        Enforces unique artifact ID, unique URI, unique POSIX path on host,
        valid SHA-256 hash format, and intra-workflow task node association,
        serializing sanitized metadata headers and BIDS entities into SQLite.

        Parameters
        ------------
        artifact: RemoteArtifact
            Pydantic remote artifact pointer to register.
        workflow_id: str
            Parent workflow identifier.
        node_id: str | None
            Optional task node identifier that produced the artifact.
            Defaults to None.

        Returns
        --------
            None: NoneType object
                Persists artifact record into remote_artifacts table.
        """
        with self.connection() as conn:
            wf_cursor: sqlite3.Cursor = conn.execute(
                "SELECT 1 FROM workflows WHERE workflow_id = ?;",
                (workflow_id,),
            )
            if wf_cursor.fetchone() is None:
                raise WorkflowNotFoundError(
                    f"Cannot register artifact: Workflow '{workflow_id}' "
                    "does not exist."
                )

            id_cursor: sqlite3.Cursor = conn.execute(
                "SELECT 1 FROM remote_artifacts WHERE artifact_id = ?;",
                (artifact.artifact_id,),
            )
            if id_cursor.fetchone() is not None:
                raise ArtifactRegistrationError(
                    f"Artifact with ID '{artifact.artifact_id}' is already "
                    "registered."
                )

            uri_cursor: sqlite3.Cursor = conn.execute(
                "SELECT 1 FROM remote_artifacts WHERE uri = ?;",
                (artifact.uri,),
            )
            if uri_cursor.fetchone() is not None:
                raise ArtifactRegistrationError(
                    f"Artifact with URI '{artifact.uri}' is already registered."
                )

            path_cursor: sqlite3.Cursor = conn.execute(
                "SELECT 1 FROM remote_artifacts WHERE host = ? "
                "AND posix_path = ?;",
                (artifact.host, artifact.posix_path),
            )
            if path_cursor.fetchone() is not None:
                raise ArtifactRegistrationError(
                    f"Artifact at POSIX path '{artifact.posix_path}' on "
                    f"host '{artifact.host}' is already registered."
                )

            sha256_pattern: str = r"^[0-9a-f]{64}$"
            if not re.match(sha256_pattern, artifact.sha256_header):
                raise ArtifactRegistrationError(
                    f"Cannot register artifact: SHA-256 header hash "
                    f"'{artifact.sha256_header}' must be a 64-character "
                    "lowercase hexadecimal string."
                )

            target_node_id: str | None = node_id or artifact.created_by_node
            if target_node_id is not None:
                node_cursor: sqlite3.Cursor = conn.execute(
                    "SELECT 1 FROM task_nodes WHERE node_id = ? AND "
                    "workflow_id = ?;",
                    (target_node_id, workflow_id),
                )
                if node_cursor.fetchone() is None:
                    raise NodeNotFoundError(
                        f"Cannot register artifact: Node '{target_node_id}' "
                        f"does not exist in workflow '{workflow_id}'."
                    )

            header_json_str: str = artifact.header_summary.model_dump_json()
            bids_json_str: str = json.dumps(artifact.bids_entities)
            created_at_iso: str = artifact.created_at.isoformat()

            try:
                conn.execute(
                    """
                    INSERT INTO remote_artifacts (
                        artifact_id, uri, workflow_id, node_id, host,
                        posix_path, modality, space, size_bytes, sha256,
                        header_json, bids_entities_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        artifact.artifact_id,
                        artifact.uri,
                        workflow_id,
                        target_node_id,
                        artifact.host,
                        artifact.posix_path,
                        artifact.modality.value,
                        artifact.space,
                        artifact.size_bytes,
                        artifact.sha256_header,
                        header_json_str,
                        bids_json_str,
                        created_at_iso,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ArtifactRegistrationError(
                    f"Database integrity constraint violated while "
                    f"registering artifact '{artifact.artifact_id}': {exc}"
                ) from exc
```

### Patch 4: Test Fixtures & Adversarial Test Alignment
The implementer/worker must apply these coordinated adjustments:

1. **`tests/conftest.py`**, line 83:
   Change `sha256_header="abcdef1234567890"` to:
   ```python
   sha256_header="abcdef1234567890" * 4,
   ```

2. **`tests/unit/test_schemas.py`**, line 175 & line 210:
   Change line 175 to `sha256_header="a1b2c3d4e5f67890" * 4,`  
   Change line 210 to:
   ```python
   sha256_header=(
       "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
   ),
   ```

3. **`tests/unit/test_schemas_adversarial.py`**, line 418:
   Change `sha256_header="0123456789abcdef"` to:
   ```python
   sha256_header="0123456789abcdef" * 4,
   ```

4. **`tests/unit/test_adversarial_blackboard_provenance.py`**:
   - Lines 284–290: Update `test_artifact_cross_workflow_node_foreign_key_behavior` to assert exception:
     ```python
     with pytest.raises(NodeNotFoundError) as exc_info:
         blackboard.register_artifact(
             art, workflow_id="wf-b", node_id="node-in-wf-a"
         )
     assert "does not exist in workflow" in str(exc_info.value)
     ```
   - Lines 291–331: Update `test_artifact_malformed_sha256_hash_accepted_silently` to `test_artifact_malformed_sha256_hash_rejected`:
     ```python
     def test_artifact_malformed_sha256_hash_rejected(
         self,
         blackboard: Blackboard,
         sample_header: SanitizedNeuroHeader,
     ) -> None:
         """Verify that malformed sha256 hash digests are rejected.

         Parameters
         ------------
         blackboard: Blackboard
             Blackboard fixture.
         sample_header: SanitizedNeuroHeader
             Sanitized header fixture.

         Returns
         --------
             None: NoneType object
                 Asserts ValidationError on malformed SHA-256 hash.
         """
         blackboard.create_workflow("wf-hash", "Malformed hash workflow")

         with pytest.raises(ValidationError):
             RemoteArtifact(
                 artifact_id="art-bad-hash-01",
                 uri="cluster-a:///data/bad_hash.nii.gz",
                 host="cluster-a",
                 posix_path="/data/bad_hash.nii.gz",
                 modality=ModalityType.T1W,
                 sha256_header="not_a_valid_hex_hash_12345",
                 size_bytes=100,
                 header_summary=sample_header,
             )
     ```

---

## 5. Verification Method

To verify these changes independently:

1. **Adversarial Blackboard Test Suite**:
   ```bash
   uv run pytest -v tests/unit/test_adversarial_blackboard_provenance.py -k "Artifact"
   ```
2. **Schema & Blackboard Unit Test Suites**:
   ```bash
   uv run pytest -v tests/unit/test_schemas.py tests/unit/test_schemas_adversarial.py tests/unit/test_blackboard.py
   ```
3. **Invalidation Conditions**:
   - `register_artifact(art, workflow_id="wf-b", node_id="node-in-wf-a")` raising anything other than `NodeNotFoundError` indicates the cross-workflow check failed.
   - Initializing `RemoteArtifact(..., sha256_header="bad_hash")` without raising `pydantic.ValidationError` indicates schema regex failure.
   - Inserting an artifact with duplicate `artifact_id` raising raw `sqlite3.IntegrityError` instead of `ArtifactRegistrationError` indicates error wrapping failure.
   - Any function missing type annotations or standard docstring format violates `python_standard.md`.
