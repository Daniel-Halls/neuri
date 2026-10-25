# BRIEFING — 2026-10-25T20:07:00Z

## Mission
Implement Milestone 3 of Neuri: Unified TelemetryTap & Circuit Breakers with 100% test pass rate and strict Python standard compliance.

## 🔒 My Identity
- Archetype: teamwork_preview_worker
- Roles: implementer, qa, specialist
- Working directory: /Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_worker_m3_1
- Original parent: 93d2f271-2e53-4e5d-a816-275a3ea34195
- Milestone: Milestone 3 (Unified TelemetryTap & Circuit Breakers)

## 🔒 Key Constraints
- Exclusive write ownership:
  - `/Users/mszdjh3/code/neuri/src/neuri/core/telemetry.py`
  - `/Users/mszdjh3/code/neuri/src/neuri/core/__init__.py`
  - `/Users/mszdjh3/code/neuri/tests/unit/test_telemetry.py`
- Do not modify files owned by other modules.
- Universal Python Standards (`python_standard.md`):
  - Max line length strictly <= 88 characters.
  - PascalCase for classes, snake_case for functions and variables.
  - Type annotations on all function/method arguments and return values.
  - Docstrings on EVERY class, function, and method with `Parameters` and `Returns` blocks.
  - ZERO module-level global variables. Encapsulate all configuration, pricing, and constants inside classes (`TelemetryConstants`, `ModelPricingTable`, etc.).
  - Single return variable per function (assign to a typed variable before returning).
  - Validated via `tests/unit/test_standards_compliance.py`.
- Integrity Mandate: Genuine logic, zero facade/hardcoded test shortcuts.
- 40 tests across 7 suites in `tests/unit/test_telemetry.py`.

## Current Parent
- Conversation ID: 93d2f271-2e53-4e5d-a816-275a3ea34195
- Updated: 2026-10-25T20:07:00Z

## Task Summary
- **What to build**: Synthesize M3 explorer designs into `src/neuri/core/telemetry.py`, update `src/neuri/core/__init__.py`, and create comprehensive 40-test suite in `tests/unit/test_telemetry.py`.
- **Success criteria**:
  1. `uv run pytest tests/unit/test_telemetry.py -v` passes (40/40 tests).
  2. `uv run pytest tests/unit/test_standards_compliance.py -v` passes (zero violations).
  3. `uv run pytest tests/unit/ -v` passes (all unit tests pass, no regressions).
- **Interface contracts**: `PROJECT.md` & explorer handoffs.
- **Code layout**: `src/neuri/core/telemetry.py`, `tests/unit/test_telemetry.py`.

## Change Tracker
- **Files modified**: None yet.
- **Build status**: Untested.
- **Pending issues**: Implementation not started.

## Quality Status
- **Build/test result**: Pending.
- **Lint status**: Pending.
- **Tests added/modified**: Pending 40 tests in `tests/unit/test_telemetry.py`.

## Loaded Skills
- None explicitly loaded.

## Key Decisions Made
- None yet.

## Artifact Index
- `DISPATCH.md` — Assignment instructions.
- `BRIEFING.md` — Working memory.
- `progress.md` — Liveness and progress tracker.
