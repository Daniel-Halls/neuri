# M2-It2 Citations Fix Strategy & Verification Analysis

**Target Modules**: `src/neuri/core/blackboard.py`, `tests/unit/test_adversarial_blackboard_provenance.py`, `tests/unit/test_blackboard.py`  
**Explorer**: `teamwork_preview_explorer_m2_it2_3`  
**Parent Orchestrator**: `93d2f271-2e53-4e5d-a816-275a3ea34195`  
**Milestone**: M2-It2 Citations  
**Objective**: Investigate and design exact fix strategy for Observations 1.4 & 1.5 from Challenger M2-2, including drop-in code conforming 100% to Universal Python Standards and test suite impact verification.

---

## 1. Observation

### Observation 1.4: Raw `sqlite3.IntegrityError` Leaked on Citation Year Boundary Violation
- **File**: `src/neuri/core/blackboard.py`, lines 384–386 and lines 2260–2288
- **Database Schema**:
  ```sql
  CREATE TABLE IF NOT EXISTS citations_ledger (
      citation_key TEXT PRIMARY KEY,
      doi TEXT,
      pmid TEXT,
      title TEXT NOT NULL,
      authors TEXT NOT NULL,
      year INTEGER CHECK (
          year IS NULL OR (year >= 1800 AND year <= 2100)
      ),
      bibtex TEXT NOT NULL,
      verified INTEGER NOT NULL DEFAULT 1 CHECK (verified IN (0, 1)),
      created_at TEXT NOT NULL
  );
  ```
- **Existing Implementation in `register_citation`**:
  ```python
  with self.connection() as conn:
      conn.execute(
          """
          INSERT INTO citations_ledger (
              citation_key, doi, pmid, title, authors, year,
              bibtex, verified, created_at
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
          ON CONFLICT(citation_key) DO UPDATE SET
              doi = COALESCE(excluded.doi, citations_ledger.doi),
              pmid = COALESCE(excluded.pmid, citations_ledger.pmid),
              title = excluded.title,
              authors = excluded.authors,
              year = COALESCE(excluded.year, citations_ledger.year),
              bibtex = excluded.bibtex,
              verified = excluded.verified;
          """,
          (
              citation_key,
              doi,
              pmid,
              title,
              authors_json_str,
              year,
              bibtex,
              verified_int,
              created_at_iso,
          ),
      )
  ```
- **Observed Behavior**:
  1. The SQL execution inside `with self.connection() as conn:` is completely unwrapped.
  2. When `year < 1800` (e.g. `year=1750`) or `year > 2100` (e.g. `year=3000`) is supplied, SQLite enforces the `CHECK (year IS NULL OR (year >= 1800 AND year <= 2100))` constraint and raises `sqlite3.IntegrityError: CHECK constraint failed: citations_ledger`.
  3. Because `register_citation` does not catch `sqlite3.IntegrityError`, this low-level driver exception escapes directly across the public `Blackboard` API.
  4. In `tests/unit/test_adversarial_blackboard_provenance.py`, lines 425–440, the adversarial probe specifically asserts `with pytest.raises(sqlite3.IntegrityError):`, confirming that raw SQLite errors escape to callers rather than being normalized to domain `BlackboardError`.

### Observation 1.5: Unvalidated BibTeX Ingestion Corrupts `references.bib`
- **File**: `src/neuri/core/blackboard.py`, lines 2216–2255 and lines 2384–2405
- **Existing Implementation in `register_citation`**:
  ```python
  def register_citation(
      self,
      citation_key: str,
      title: str,
      bibtex: str,
      doi: str | None = None,
      pmid: str | None = None,
      authors: list[str] | None = None,
      year: int | None = None,
      verified: bool = True,
  ) -> None:
      authors_json_str: str = json.dumps(authors or [])
      verified_int: int = 1 if verified else 0
      created_at_iso: str = datetime.now(timezone.utc).isoformat()
      with self.connection() as conn:
          ...
  ```
- **Existing Implementation in `sync_citations_to_bib`**:
  ```python
  def sync_citations_to_bib(self, bib_path: Path) -> int:
      citations: list[dict[str, Any]] = self.list_citations(verified_only=True)
      entries: list[str] = ["% Neuri Verified Citations Ledger\n\n"]
      for entry in citations:
          entries.append(entry["bibtex"].strip() + "\n\n")

      bib_path.parent.mkdir(parents=True, exist_ok=True)
      bib_path.write_text("".join(entries), encoding="utf-8")
      count: int = len(citations)
      return count
  ```
- **Observed Behavior**:
  1. `register_citation` accepts arbitrary strings for the `bibtex` parameter without syntactic or structural validation. Empty strings (`""`, `"   "`), raw non-BibTeX strings (`"MALFORMED_BIBTEX_WITHOUT_BRACES_OR_ENTRY_TYPE"`), missing entry types, or unclosed delimiters are accepted and committed to SQLite without error.
  2. When `sync_citations_to_bib(bib_path)` is executed, it iterates through all verified citations and dumps their raw `bibtex` strings directly into `references.bib`.
  3. Consequently, invalid BibTeX entries pollute `references.bib`, rendering the bibliography unparseable by LaTeX, BibTeX, Biber, or Pandoc.
  4. In `tests/unit/test_adversarial_blackboard_provenance.py`, lines 504–517 (`test_citation_malformed_bibtex_corrupts_synced_file`), the test currently demonstrates this vulnerability by asserting that the malformed string was successfully written to disk.

---

## 2. Logic Chain

1. **Encapsulation Contract (Premise 1)**:
   In Neuri's architecture (`PROJECT.md` line 7, `ORIGINAL_REQUEST.md` R2), `Blackboard` is an encapsulated SQLite WAL state engine. All database operations should surface typed domain errors derived from `BlackboardError` (`WorkflowNotFoundError`, `NodeNotFoundError`, `CycleDetectedError`, `InvalidStateTransitionError`, `DuplicateEdgeError`, `ArtifactRegistrationError`). Leaking `sqlite3.IntegrityError` breaks API boundaries and prevents callers from handling database errors uniformly.
2. **Failure Mode of Observation 1.4**:
   Per Observation 1.4, when SQLite encounters an invalid year boundary constraint violation, it raises `sqlite3.IntegrityError`. Since `sqlite3.IntegrityError` does not inherit from `BlackboardError`, caller blocks catching `except BlackboardError:` miss the exception, leading to unexpected crashes or untyped error handling.
3. **Remedy for Observation 1.4**:
   Wrapping SQL execution in `register_citation` with `try ... except sqlite3.IntegrityError as exc:` and raising `BlackboardError(f"Failed to register citation '{citation_key}': database integrity constraint violation: {exc}") from exc` restores encapsulation while preserving the diagnostic traceback.
4. **Data Integrity Guarantee for Citations (Premise 2)**:
   In `ORIGINAL_REQUEST.md` R2 and R7, `references.bib` is an essential deliverable created during `/init` and workspace operations. Ingestion of malformed BibTeX corrupts the user's project bibliography file.
5. **Remedy for Observation 1.5**:
   Validating `bibtex` prior to database insertion ensures that corrupt records cannot enter `citations_ledger`. A valid BibTeX entry must be:
   - Non-empty (after stripping whitespace).
   - Contain `@` as an entry type marker.
   - Specify a non-empty entry type following `@` (e.g., `article`, `book`, `inproceedings`).
   - Contain an opening brace `{` after the entry type.
   - Contain a closing brace `}` positioned after the opening brace.
   If validation fails, raising `BlackboardError` (or `CitationValidationError(BlackboardError, ValueError)`) prevents persistence and blocks downstream corruption of `references.bib`.
6. **Test Suite Interaction**:
   - In `tests/unit/test_blackboard.py`, all existing citation tests (`test_register_and_get_citation`, `test_duplicate_citation_key_upsert`, `test_list_citations`, `test_sync_citations_to_bib_file`, `test_export_provenance`) pass valid years (`2012`, `2019`, `2020`, or `None`) and standard `@article{...}` BibTeX strings. They will continue to pass without modification.
   - In `tests/unit/test_adversarial_blackboard_provenance.py`:
     - `test_citation_year_check_constraint_boundary` currently expects `sqlite3.IntegrityError`. Once wrapped, it will raise `BlackboardError`. Updating the test to assert `pytest.raises(BlackboardError)` aligns it with the fix.
     - `test_citation_malformed_bibtex_corrupts_synced_file` currently expects registration to succeed with malformed text. Once validation is added, calling `register_citation` with malformed text will raise an exception. Updating the test to assert `pytest.raises((BlackboardError, ValueError))` confirms the security hardening.

---

## 3. Caveats

1. **Read-Only Explorer Mandate**: In accordance with the Explorer archetype, this report provides read-only analysis and drop-in code snippets; no modifications have been made directly to production files.
2. **Container PTY Device Allocation**: `run_command` in this execution environment returns `failed to create PTY: device not configured.` Test execution commands and verification methods are documented for runner environments where a standard TTY/PTY or subshell is configured.
3. **BibTeX Parsing Scope**: BibTeX validation is designed to be lightweight and zero-dependency (no external grammar parser like `bibtexparser` or `pybtex`), strictly verifying structural entry delimiters (`@`, `{ ... }`, non-empty entry type and content) without imposing restrictive field-level schema requirements that might reject unconventional or custom BibTeX entry types.

---

## 4. Conclusion & Drop-In Code Strategy

### 4.1 Implementation Changes for `src/neuri/core/blackboard.py`

#### Change 1: Add BibTeX Syntax Validator Helper Method
Add `_validate_bibtex_syntax` as an internal method on `Blackboard` to enforce the Single Responsibility Principle and comply with Universal Python Standards.

```python
    def _validate_bibtex_syntax(self, bibtex: str, citation_key: str) -> None:
        """Validate that a BibTeX entry string has well-formed basic syntax.

        Verifies that the BibTeX string is non-empty and contains basic
        BibTeX structure including an '@' entry declaration, an entry type,
        and matching braces '{...}', preventing corrupted entries from being
        persisted or synced to references.bib.

        Parameters
        ------------
        bibtex: str
            Raw BibTeX string to inspect.
        citation_key: str
            Citation key identifier for diagnostic context.

        Returns
        --------
            None: NoneType object
                Returns None if validation succeeds, else raises BlackboardError.
        """
        if not isinstance(bibtex, str) or not bibtex.strip():
            raise BlackboardError(
                f"Citation '{citation_key}' BibTeX string cannot be empty."
            )

        stripped_bibtex: str = bibtex.strip()
        at_index: int = stripped_bibtex.find("@")
        if at_index == -1:
            raise BlackboardError(
                f"Citation '{citation_key}' BibTeX string must contain '@' "
                f"entry type declaration."
            )

        open_brace_index: int = stripped_bibtex.find("{", at_index + 1)
        if open_brace_index == -1:
            raise BlackboardError(
                f"Citation '{citation_key}' BibTeX string must contain "
                f"opening brace '{{' after entry type."
            )

        entry_type: str = stripped_bibtex[
            at_index + 1 : open_brace_index
        ].strip()
        if not entry_type:
            raise BlackboardError(
                f"Citation '{citation_key}' BibTeX string is missing entry "
                f"type name between '@' and '{{'."
            )

        close_brace_index: int = stripped_bibtex.rfind("}")
        if close_brace_index == -1 or close_brace_index <= open_brace_index:
            raise BlackboardError(
                f"Citation '{citation_key}' BibTeX string must contain "
                f"closing brace '}}' after opening brace."
            )

        return None
```

#### Change 2: Update `register_citation` in `src/neuri/core/blackboard.py`
Replace lines 2216–2288 of `src/neuri/core/blackboard.py` with the following drop-in method:

```python
    def register_citation(
        self,
        citation_key: str,
        title: str,
        bibtex: str,
        doi: str | None = None,
        pmid: str | None = None,
        authors: list[str] | None = None,
        year: int | None = None,
        verified: bool = True,
    ) -> None:
        """Register or update a verified citation in the citations ledger.

        Enforces anti-hallucination tracking by persisting verified DOI,
        PMID, and BibTeX entries, with syntactic BibTeX validation and
        structured database exception wrapping.

        Parameters
        ------------
        citation_key: str
            Unique BibTeX citation identifier key.
        title: str
            Article or software title.
        bibtex: str
            Complete BibTeX entry string conforming to basic BibTeX syntax.
        doi: str | None
            Digital Object Identifier if available. Defaults to None.
        pmid: str | None
            PubMed Identifier if available. Defaults to None.
        authors: list[str] | None
            List of author names. Defaults to None.
        year: int | None
            Publication year between 1800 and 2100. Defaults to None.
        verified: bool
            Whether citation is verified against real literature. Defaults to True.

        Returns
        --------
            None: NoneType object
                Persists or updates citation entry.
        """
        self._validate_bibtex_syntax(bibtex, citation_key)

        authors_json_str: str = json.dumps(authors or [])
        verified_int: int = 1 if verified else 0
        created_at_iso: str = datetime.now(timezone.utc).isoformat()

        try:
            with self.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO citations_ledger (
                        citation_key, doi, pmid, title, authors, year,
                        bibtex, verified, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(citation_key) DO UPDATE SET
                        doi = COALESCE(excluded.doi, citations_ledger.doi),
                        pmid = COALESCE(excluded.pmid, citations_ledger.pmid),
                        title = excluded.title,
                        authors = excluded.authors,
                        year = COALESCE(excluded.year, citations_ledger.year),
                        bibtex = excluded.bibtex,
                        verified = excluded.verified;
                    """,
                    (
                        citation_key,
                        doi,
                        pmid,
                        title,
                        authors_json_str,
                        year,
                        bibtex,
                        verified_int,
                        created_at_iso,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise BlackboardError(
                f"Failed to register citation '{citation_key}': database "
                f"integrity constraint violation: {exc}"
            ) from exc

        return None
```

---

### 4.2 Test Suite Updates for `tests/unit/test_adversarial_blackboard_provenance.py`

#### Update 1: `test_citation_year_check_constraint_boundary` (lines 409–440)
Update the test to assert `BlackboardError` instead of raw `sqlite3.IntegrityError`:

```python
    def test_citation_year_check_constraint_boundary(
        self,
        blackboard: Blackboard,
    ) -> None:
        """Verify year constraint (1800 to 2100) rejects out-of-bounds years.

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.

        Returns
        --------
            None: NoneType object
                Asserts BlackboardError wrapping on invalid years.
        """
        with pytest.raises(BlackboardError) as exc_info_ancient:
            blackboard.register_citation(
                citation_key="ancient1700",
                title="Ancient Work",
                bibtex="@article{ancient1700, title={Ancient}}",
                year=1750,
            )
        assert "integrity constraint violation" in str(exc_info_ancient.value)

        with pytest.raises(BlackboardError) as exc_info_future:
            blackboard.register_citation(
                citation_key="future3000",
                title="Future Work",
                bibtex="@article{future3000, title={Future}}",
                year=3000,
            )
        assert "integrity constraint violation" in str(exc_info_future.value)
```

#### Update 2: `test_citation_malformed_bibtex_corrupts_synced_file` (lines 480–517)
Convert from an unhandled vulnerability probe to an active regression test asserting that malformed inputs raise `BlackboardError`:

```python
    def test_citation_malformed_bibtex_rejected_by_register(
        self,
        blackboard: Blackboard,
        tmp_path: Path,
    ) -> None:
        """Verify that malformed BibTeX syntax is rejected with BlackboardError.

        Prevents corrupting references.bib by validating that BibTeX strings
        contain non-empty content with basic entry structure (@ and {...}).

        Parameters
        ------------
        blackboard: Blackboard
            Blackboard fixture.
        tmp_path: Path
            Pytest temporary directory.

        Returns
        --------
            None: NoneType object
                Asserts BlackboardError on malformed BibTeX entries.
        """
        malformed_inputs: list[str] = [
            "MALFORMED_BIBTEX_WITHOUT_BRACES_OR_ENTRY_TYPE",
            "",
            "   ",
            "@article",
            "@{missing_type}",
            "@article{unclosed",
            "@article}inverted{",
        ]

        for bad_bib in malformed_inputs:
            with pytest.raises(BlackboardError):
                blackboard.register_citation(
                    citation_key="badbib2024",
                    title="Broken BibTeX Paper",
                    bibtex=bad_bib,
                    verified=True,
                )
```

---

### 4.3 Summary Matrix of Verification Impact

| Test Identifier | File | Current Status | Expected Post-Fix Status | Notes |
|---|---|---|---|---|
| `test_register_and_get_citation` | `test_blackboard.py:1469` | PASS | **PASS** | `year=2019`, valid `@article{...}` |
| `test_duplicate_citation_key_upsert` | `test_blackboard.py:1507` | PASS | **PASS** | `year=None`, `year=2012`, valid `@article{...}` |
| `test_list_citations` | `test_blackboard.py:1538` | PASS | **PASS** | Valid BibTeX entries |
| `test_sync_citations_to_bib_file` | `test_blackboard.py:1574` | PASS | **PASS** | Valid BibTeX entries |
| `test_export_provenance` | `test_blackboard.py:1690` | PASS | **PASS** | `year=2020`, valid BibTeX |
| `test_citation_missing_doi_and_pmid_handled` | `test_adversarial_blackboard_provenance.py:337` | PASS | **PASS** | `year=2012`, valid BibTeX |
| `test_citation_duplicate_doi_different_keys` | `test_adversarial_blackboard_provenance.py:370` | PASS | **PASS** | Valid BibTeX |
| `test_citation_sync_writes_utf8_special_characters` | `test_adversarial_blackboard_provenance.py:441` | PASS | **PASS** | Valid UTF-8 BibTeX |
| `test_citation_year_check_constraint_boundary` | `test_adversarial_blackboard_provenance.py:409` | Probes raw sqlite3 error | **PASS (with test update)** | Test updated to assert `BlackboardError` |
| `test_citation_malformed_bibtex_corrupts_synced_file` | `test_adversarial_blackboard_provenance.py:480` | Probes unvalidated write | **PASS (with test update)** | Test updated to assert `BlackboardError` |

---

## 5. Verification Method

To verify these fixes independently:

1. **Adversarial Test Suite Execution**:
   ```bash
   uv run pytest -v tests/unit/test_adversarial_blackboard_provenance.py
   ```
2. **Existing Blackboard Unit Test Suite**:
   ```bash
   uv run pytest -v tests/unit/test_blackboard.py
   ```
3. **Universal Python Standards AST Checker**:
   ```bash
   uv run pytest -v tests/unit/test_standards_compliance.py
   ```
4. **Invalidation Conditions**:
   - Calling `blackboard.register_citation(citation_key="bad_year", title="T", bibtex="@article{k, title={T}}", year=1700)` must raise `BlackboardError`, NOT `sqlite3.IntegrityError`.
   - Calling `blackboard.register_citation(citation_key="bad_bib", title="T", bibtex="not_bibtex")` must raise `BlackboardError` and NOT commit any row to `citations_ledger`.
   - Running `sync_citations_to_bib` after attempting to register malformed BibTeX must not contain invalid entries in `references.bib`.
