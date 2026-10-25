# Comprehensive Survey Report: Codebase Layout, Packaging, Testing Harness & Python Standards (Phase 1)

**Agent Role**: Codebase Explorer (Survey 3)  
**Working Directory**: `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_survey_3/`  
**Date**: 2026-10-25  

---

## 1. Observation

### 1.1 Existing Repository State
Direct filesystem inspection of `/Users/mszdjh3/code/neuri` via directory listing and pattern search revealed:
- **Files present**:
  - `README.md` (1 line, 7 bytes: `# neuri`)
  - `LICENSE` (25 lines, 1,211 bytes: The Unlicense)
  - `.gitignore` (224 lines, 4,697 bytes; line 2 explicitly ignores `technical_documenation/*`)
  - `technical_documenation/NEURI_ARCHITECTURE_AND_IMPLEMENTATION_PLAN.md` (573 lines, 45,250 bytes)
  - `.agents/` metadata directory containing teamwork coordination state
- **Missing Directories & Files**:
  - No `pyproject.toml` or `uv.lock` exists in the repository.
  - No `src/` directory exists (target package `src/neuri/` is not yet created).
  - No `tests/` directory exists (unit, adapter, and e2e test suites are missing).
  - No `skills/` directory exists (Tier-0 compact catalog `skills/index.yaml` is missing).
  - No `.neuri/` runtime state directory exists (target for `neuri init`).
  - No `phase1_implementation_plan.md` exists in the root directory (the acceptance criteria require saving the approved plan to `technical_documenation/PHASE_1_IMPLEMENTATION_PLAN.md`).

### 1.2 Execution Environment Observation
Execution of `run_command` in this session yielded:
```text
Command failed to run: failed to create PTY: device not configured.
```
This indicates that the current execution container does not have an allocated pseudo-terminal (PTY) device. Consequently, direct interactive TTY commands cannot run through `run_command`. Automated verification must rely on headless CLI invocation (`CliRunner` / non-interactive CLI flags) and stream mock fixtures (`asyncio.StreamReader` / replay files).

### 1.3 Key Requirements & Documentation Quotes
- **ORIGINAL_REQUEST.md (lines 5, 18)**:
  > "Implement Phase 1 of Neuri, a vendor-agnostic neuroscience meta-harness. Deliver a fully functioning, tested Python 3.12+ package managed by uv, featuring an `agy`-style interactive terminal chat interface with slash commands, a GUI-ready session engine, SQLite WAL Blackboard, TelemetryTap with circuit breakers, and Tier-1 BaseHarnessAdapter drivers for Antigravity (`agy`) and OpenAI Codex CLI (`codex`)."
  > "Set up `pyproject.toml` managed via `uv` with Python >=3.12, registering the `neuri` CLI script and dependencies (`pydantic>=2.7`, `typer>=0.12`, `rich>=13.7`, `textual>=0.80`, `pyyaml>=6.0`, `tomli-w>=1.0`, `httpx>=0.27`, `pytest>=8.2`, `pytest-asyncio>=0.24`)."
- **ORIGINAL_REQUEST.md (lines 51–55, 78)**:
  > "Strict PEP 8 styling (snake_case, PascalCase, 4-space indent, 79–88 char line limit). Type hints on all function arguments, class methods, and return values. Mandatory custom docstring format on every class, method, and function. Single responsibility principle, single return variable/type, zero global variables."
- **python_standard.md (lines 9–14, 17–38)**:
  > "- CRITICAL: ALWAYS follow strict PEP 8 style guidelines for all Python code...
  > - ALWAYS include type hints for all function arguments and return values.
  > - YOU MUST document every Python function, method, and class using my preferred docstring format below. NEVER leave a function undocumented.
  > - NEVER define global variables, if global variables are needed think about changing it to a class.
  > - Functions should ALWAYS return one type and a single variable...
  > - Functions should only perform one action and do one thing well."

---

## 2. Logic Chain

### 2.1 Codebase Layout & Directory Architecture
From Observation 1.1, the repository is an uninitialized greenfield project containing only documentation and licensing. To satisfy R1, R2, R4, R6, R7, and Section 6 of `NEURI_ARCHITECTURE_AND_IMPLEMENTATION_PLAN.md`, the repository must be structured as follows:

```text
neuri/
├── pyproject.toml                         # Packaging, dependencies, scripts, tool configs
├── README.md                              # Project overview and CLI quickstart
├── LICENSE                                # Public domain unlicense
├── technical_documenation/
│   ├── NEURI_ARCHITECTURE_AND_IMPLEMENTATION_PLAN.md
│   └── PHASE_1_IMPLEMENTATION_PLAN.md    # Approved implementation plan
├── skills/
│   └── index.yaml                         # Tier-0 compact router index (<300 tokens, 7 skills)
├── src/
│   └── neuri/
│       ├── __init__.py                    # Package export and __version__ = "0.1.0"
│       ├── cli/
│       │   ├── __init__.py
│       │   └── main.py                    # Typer CLI entrypoint (`neuri`, `-p`, `--dry-run`)
│       ├── ui/
│       │   ├── __init__.py
│       │   └── terminal_chat.py           # Textual interactive chat UI
│       ├── core/
│       │   ├── __init__.py
│       │   ├── schemas.py                 # Pydantic models (SanitizedNeuroHeader, RemoteArtifact, etc.)
│       │   ├── config.py                  # Two-tier TOML configuration loader (~/.neuri + .neuri)
│       │   ├── blackboard.py              # SQLite WAL Blackboard (7 tables, DAG, provenance)
│       │   ├── telemetry.py               # TelemetryTap, event normalization, circuit breakers
│       │   ├── preflight.py               # Deterministic zero-token pre-flight validator
│       │   ├── orchestrator.py            # DAG execution, bounded retry N=2, WAITING_OPERATOR
│       │   ├── slash_commands.py          # Slash command registry & handlers
│       │   └── session.py                 # NeuriSessionEngine UI-agnostic session controller
│       └── adapters/
│           ├── __init__.py
│           ├── base.py                    # BaseHarnessAdapter abstract protocol
│           ├── antigravity.py             # Tier-1 AntigravityAdapter (agy)
│           ├── codex.py                   # Tier-1 CodexAdapter (codex)
│           ├── opencode.py                # Tier-2 OpenCodeAdapter stub
│           ├── openclaw.py                # Tier-2 OpenClawAdapter stub
│           ├── ollama_local.py            # Tier-2 OllamaAdapter stub
│           └── registry.py                # AdapterRegistry factory
└── tests/
    ├── __init__.py
    ├── conftest.py                        # Common fixtures (temporary workspaces, dummy schemas)
    ├── fixtures/                          # Deterministic stream replay data
    │   ├── agy_stream_sample.ndjson
    │   ├── agy_breaker_sample.ndjson
    │   ├── codex_stream_sample.ndjson
    │   └── codex_error_sample.ndjson
    ├── unit/
    │   ├── __init__.py
    │   ├── test_schemas.py
    │   ├── test_config.py
    │   ├── test_blackboard.py
    │   ├── test_telemetry.py
    │   ├── test_preflight.py
    │   ├── test_orchestrator.py
    │   ├── test_slash_commands.py
    │   ├── test_session.py
    │   └── test_standards_compliance.py   # AST-based Python standards enforcement
    ├── adapters/
    │   ├── __init__.py
    │   ├── test_base_adapter.py
    │   ├── test_antigravity_adapter.py
    │   ├── test_codex_adapter.py
    │   └── test_registry.py
    └── e2e/
        ├── __init__.py
        ├── test_cli_headless.py
        └── test_workspace_init.py
```

### 2.2 Dependencies & Build Configuration (`pyproject.toml`)
Based on Observation 1.3, `pyproject.toml` must be managed via `uv`, targeting Python `>=3.12`. The modern build backend is `hatchling`.
- **Runtime Dependencies**:
  - `pydantic>=2.7.0`: Strict schema validation, literal types (`phi_sanitized: Literal[True]`), immutable data structures.
  - `typer>=0.12.0`: CLI parameter parsing, headless subcommands, interactive flag routing.
  - `rich>=13.7.0`: Formatted terminal tables, syntax highlighting, progress bars.
  - `textual>=0.80.0`: TUI framework for terminal chat, collapsible reasoning containers, reactive widgets.
  - `pyyaml>=6.0`: Parsing Tier-0 skill index (`skills/index.yaml`).
  - `tomli-w>=1.0.0`: Writing TOML workspace configuration files (`neuri.toml`).
  - `httpx>=0.27.0`: Async HTTP client for Tier-2 Ollama adapter and MCP endpoints.
- **Development & Testing Dependencies**:
  - `pytest>=8.2.0`: Test runner.
  - `pytest-asyncio>=0.24.0`: Asynchronous test execution for coroutines and async streams.
  - `pytest-mock>=3.14.0`: Subprocess and filesystem mocking.
  - `ruff>=0.4.0`: Fast PEP 8 linting and formatting.
  - `mypy>=1.10.0`: Strict static type verification.
- **Entry Points**:
  - Register `neuri = "neuri.cli.main:app"` under `[project.scripts]`.

### 2.3 Test Suite Architecture & Verification Strategy
To satisfy Acceptance Criteria 1, 4, and 5 without external API dependencies or live LLMs:
1. **Tier 1 (Unit Tests)**:
   - Verify isolated components: Pydantic schemas, two-tier config resolution, SQLite table creation & WAL mode, `TelemetryTap` event parsing and circuit breaker thresholds, preflight validation logic, orchestrator DAG topological ordering, and slash command parsing.
2. **Tier 2 (Adapter Stream Replay)**:
   - Replay recorded NDJSON/JSONL logs from `tests/fixtures/` directly into `AntigravityAdapter` and `CodexAdapter` using mock async streams.
   - Assert `<thinking>` tag extraction, `ThinkingDelta` events, `TokenUsageUpdate` accumulations, and tool failure circuit breaker tripping.
3. **Tier 3 (E2E Headless CLI Tests)**:
   - Use Typer's `CliRunner` to verify `neuri -p "/skills"`, `neuri -p "/status"`, `neuri -p "/init"`, and `neuri -p "<prompt>" --dry-run`.
   - Verify `.neuri/` workspace scaffolding (`neuri.toml`, `state.db`, `references.bib`, `execution_history.json`, `qa_snapshots/`).
4. **Tier 4 (UI Event Tests)**:
   - Use Textual's `app.run_test()` to headless-test widget rendering, collapsible `<thinking>` containers, and autocompletion events.

### 2.4 Universal Python Standards (R8) Enforcement Mechanism
To eliminate human error and ensure strict compliance with `/Users/mszdjh3/.gemini/config/rules/python_standard.md`:
- Every function, method, and class must include the specified docstring template:
  ```python
  def function_name(param1: int, param2: str = "default") -> bool:
      """Brief one-line summary of what the function does.

      Optional extended description explaining complex logic, side effects, 
      or edge cases if necessary.

      Parameters
      ------------
      param1: int  
          Description of the first parameter.
      param2: str
          Description of the second parameter. Defaults to "default".

      Returns
      --------
          bool: boolean object 
              Description of the return value.
      """
  ```
- **AST Compliance Linter (`tests/unit/test_standards_compliance.py`)**:
  - Parse the AST of every `.py` file under `src/neuri/`.
  - Assert that all `FunctionDef` and `AsyncFunctionDef` have full type annotations (`returns` is not None, arguments have `annotation`).
  - Assert that docstrings contain `Parameters\n------------` (when arguments exist) and `Returns\n--------`.
  - Assert no module-level global variables exist (constants inside classes or typing declarations only).
  - Assert all return statements return a single value or typed container.

### 2.5 Inter-Module Dependency Graph & Implementation Sequencing
Dependencies strictly dictate implementation sequence:
- **Phase 1.1**: Package scaffolding (`pyproject.toml`, directory structure, `skills/index.yaml`).
- **Phase 1.2**: Core data contracts (`src/neuri/core/schemas.py`, `src/neuri/core/config.py`).
- **Phase 1.3**: Persistence & Telemetry (`src/neuri/core/blackboard.py`, `src/neuri/core/telemetry.py`).
- **Phase 1.4**: Harness Adapter Layer (`src/neuri/adapters/base.py`, `antigravity.py`, `codex.py`, `registry.py`, tier-2 stubs).
- **Phase 1.5**: Pre-flight Validator & Orchestrator (`src/neuri/core/preflight.py`, `src/neuri/core/orchestrator.py`).
- **Phase 1.6**: Slash Commands & Session Engine (`src/neuri/core/slash_commands.py`, `src/neuri/core/session.py`).
- **Phase 1.7**: CLI Entrypoint & Textual UI (`src/neuri/cli/main.py`, `src/neuri/ui/terminal_chat.py`).
- **Phase 1.8**: Test Harness, NDJSON Fixtures & Compliance Suite (`tests/fixtures/`, `tests/unit/`, `tests/adapters/`, `tests/e2e/`).

---

## 3. Caveats

1. **PTY Availability in Subagent Environment**:
   As noted in Observation 1.2, `run_command` in this execution environment fails with `failed to create PTY: device not configured`. Testing and CLI verification must be designed so that all commands can run non-interactively via Typer `CliRunner` and headless flags (`-p` / `--print`), and adapters must support headless streaming without requiring a physical PTY.
2. **Missing `phase1_implementation_plan.md` in Root**:
   `ORIGINAL_REQUEST.md` references `phase1_implementation_plan.md`, but no such file was present in the repo root. However, the exact requirements are documented in `ORIGINAL_REQUEST.md` and `technical_documenation/NEURI_ARCHITECTURE_AND_IMPLEMENTATION_PLAN.md`. Furthermore, Acceptance Criterion 6 requires saving the approved plan to `technical_documenation/PHASE_1_IMPLEMENTATION_PLAN.md`.
3. **`.gitignore` Line 2**:
   `.gitignore` currently contains `technical_documenation/*`. If documentation changes need to be committed to git, this line may need to be adjusted or files force-added.

---

## 4. Conclusion

1. **Architecture Ready for Implementation**: The Phase 1 scope is fully specified, coherent, and cleanly modularized into 7 execution layers.
2. **Zero-Key Deterministic Replay**: All harness interactions (`agy` and `codex`) can and must be tested deterministically using NDJSON replay stream fixtures, completely isolating CI and developer testing from paid API keys or network flakiness.
3. **Automated Standards Enforcement**: The Universal Python Coding Standards (`python_standard.md`) can be strictly verified programmatically via an AST compliance test fixture (`test_standards_compliance.py`) alongside `ruff` and `mypy`.
4. **Clean Packaging**: Setting up `pyproject.toml` with `hatchling` and the specified dependencies establishes a solid foundation for `uv`-managed development.

---

## 5. Verification Method

To independently verify the recommendations and requirements in this report:

1. **Inspect Repo State**:
   ```bash
   ls -la /Users/mszdjh3/code/neuri
   ```
   Confirm absence of `pyproject.toml`, `src/`, and `tests/`.
2. **Inspect Requirements & Standards**:
   - Verify docstring format in `/Users/mszdjh3/.gemini/config/rules/python_standard.md`.
   - Verify requirement scope in `/Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md`.
   - Verify architectural tiers in `/Users/mszdjh3/code/neuri/technical_documenation/NEURI_ARCHITECTURE_AND_IMPLEMENTATION_PLAN.md`.
3. **Post-Implementation Acceptance Verification**:
   - `uv sync --all-extras` (Dependency installation)
   - `uv run pytest -v` (Zero test failures across unit, adapter, and e2e suites)
   - `uv run neuri -p "/skills"` (Tier-0 skills index renders cleanly)
   - `uv run neuri -p "/init"` (Valid `.neuri/` workspace created)
   - `uv run neuri -p "Preprocess sub-01 scan" --dry-run` (DAG generated without execution)
   - AST compliance test passes verifying 100% adherence to docstrings, typing, 0 globals, and single returns.
