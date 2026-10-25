# Task Assignment: Implement Milestone 1 (M1)

## Identity
- Role: M1 Implementation Worker
- Working directory: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_worker_m1/
- Project root: /Users/mszdjh3/code/neuri

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Mandatory Inputs to Read
1. `/Users/mszdjh3/code/neuri/.agents/teamwork/ORIGINAL_REQUEST.md`
2. `/Users/mszdjh3/code/neuri/PROJECT.md`
3. `/Users/mszdjh3/.gemini/config/rules/python_standard.md`
4. `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m1_1/handoff.md`
5. `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m1_2/handoff.md`
6. `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m1_3/handoff.md`
7. Proposed files in `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m1_3/` (`proposed_config.py`, `proposed_test_schemas.py`, `proposed_test_config.py`, `proposed_conftest.py`)

## File Ownership (Exclusively owned by this worker)
- `pyproject.toml`
- `skills/index.yaml`
- `src/neuri/__init__.py`
- `src/neuri/core/__init__.py`
- `src/neuri/core/schemas.py`
- `src/neuri/core/config.py`
- `tests/conftest.py`
- `tests/unit/__init__.py`
- `tests/unit/test_schemas.py`
- `tests/unit/test_config.py`

## Implementation Scope
1. **Packaging**: Create `pyproject.toml` per `explorer_m1_1/handoff.md` with hatchling backend, Python >=3.12, all runtime/test dependencies, typer entrypoint, ruff/mypy configs, and pytest-asyncio scope.
2. **Compact Catalog**: Create `skills/index.yaml` indexing the 7 public neuroscience skill packs, strictly under 300 tokens (<250 tokens target).
3. **Core Schemas**: Implement `src/neuri/core/schemas.py` with all 13 Pydantic v2 data models and enums per `explorer_m1_2/handoff.md`. Enforce `phi_sanitized: Literal[True] = True` on `SanitizedNeuroHeader`.
4. **Two-Tier Config**: Implement `src/neuri/core/config.py` per `explorer_m1_3/handoff.md` with `load_config`, `init_workspace`, and models.
5. **Universal Python Standards**: Every file must strictly conform to `/Users/mszdjh3/.gemini/config/rules/python_standard.md`:
   - PEP 8, 4 spaces, 79–88 char line length.
   - Strict type hints on all arguments, methods, and return values.
   - Mandatory preferred docstrings with `Parameters` and `Returns` on every class, method, and function.
   - Zero global variables. Single return type/variable. Single responsibility.
6. **Tests**: Create `tests/conftest.py`, `tests/unit/test_schemas.py`, and `tests/unit/test_config.py` and run verification.

## Verification & Reporting
1. Run `uv sync --all-extras` or test invocation if possible. Note: if terminal PTY is not available in `run_command`, use direct python execution (e.g. `python -m pytest tests/unit/test_schemas.py tests/unit/test_config.py -v`).
2. Verify all tests pass with 0 failures.
3. Write `handoff.md` in `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_worker_m1/handoff.md` documenting all files created, tests executed, outputs, and layout compliance.
4. Send a message to the orchestrator upon completion.


## 2026-10-25T15:23:21Z
[Message] timestamp=2026-10-25T15:23:21Z sender=93d2f271-2e53-4e5d-a816-275a3ea34195 priority=MESSAGE_PRIORITY_HIGH content=You are worker_m1.
Your working directory is: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_worker_m1/
Please read your task assignment at: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_worker_m1/DISPATCH.md
