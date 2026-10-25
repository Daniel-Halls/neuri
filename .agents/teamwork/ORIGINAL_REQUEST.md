# Original User Request

## 2026-10-25T15:04:41Z

Implement Phase 1 of Neuri, a vendor-agnostic neuroscience meta-harness. Deliver a fully functioning, tested Python 3.12+ package managed by uv, featuring an `agy`-style interactive terminal chat interface with slash commands, a GUI-ready session engine, SQLite WAL Blackboard, TelemetryTap with circuit breakers, and Tier-1 BaseHarnessAdapter drivers for Antigravity (`agy`) and OpenAI Codex CLI (`codex`).

Working directory: /Users/mszdjh3/code/neuri
Integrity mode: development

## Reference Documentation
- Architecture Spec: `technical_documenation/NEURI_ARCHITECTURE_AND_IMPLEMENTATION_PLAN.md`
- Implementation Plan: `phase1_implementation_plan.md`
- Universal Python Standards: `/Users/mszdjh3/.gemini/config/rules/python_standard.md`

## Requirements

### R1. Package Scaffolding, Schemas & Two-Tier Configuration
- Set up `pyproject.toml` managed via `uv` with Python >=3.12, registering the `neuri` CLI script and dependencies (`pydantic>=2.7`, `typer>=0.12`, `rich>=13.7`, `textual>=0.80`, `pyyaml>=6.0`, `tomli-w>=1.0`, `httpx>=0.27`, `pytest>=8.2`, `pytest-asyncio>=0.24`).
- Implement `src/neuri/core/schemas.py` defining strict Pydantic models: `ModalityType`, `SanitizedNeuroHeader` (enforcing `phi_sanitized: Literal[True]`), `RemoteArtifact`, `TaskState`, `TaskNode`, `TaskEdge`, `NeuriTaskEnvelope`, `NeuriTaskResult`, `TelemetryEvent`, `NiiVueLayerSpec`, `NiiVueSceneSpec`, `ChatRole`, `ChatTurn`, and `SessionEvent`.
- Implement `src/neuri/core/config.py` loading two-tier configuration (`~/.neuri/config.toml` defaults merged with `.neuri/neuri.toml` project overrides).
- Author `skills/index.yaml` Tier-0 compact catalog (<300 tokens) with the 7 public neuroscience skill packs.

### R2. SQLite WAL Blackboard & Provenance Store
- Implement `src/neuri/core/blackboard.py` backed by `.neuri/state.db` in SQLite `WAL` mode (`PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;`).
- Create and manage the 7 core tables: `workflows`, `task_nodes`, `task_edges`, `remote_artifacts`, `remote_jobs`, `telemetry_events`, and `citations_ledger`.
- Implement atomic CRUD, topological DAG queries (`get_ready_nodes`), state transitions, artifact registration, and provenance logging (`.neuri/execution_history.json`).

### R3. Unified TelemetryTap & Circuit Breakers
- Implement `src/neuri/core/telemetry.py` providing `TelemetryTap` and `CircuitBreakerTripped`.
- Normalize raw stream inputs and `<thinking>` blocks into typed `ThinkingDelta`, `TokenUsageUpdate`, `ToolCallLifecycle`, and `CircuitBreakerAlert` events.
- Enforce hard limits: `max_node_tokens`, `max_workflow_cost_usd`, and consecutive identical tool failure breakers (threshold 3).

### R4. Vendor-Agnostic Harness Adapter Layer
- Implement `src/neuri/adapters/base.py` (`BaseHarnessAdapter`) supporting dual-mode execution (headless structured JSON streaming per DAG node + interactive PTY pass-through).
- Implement Tier-1 `AntigravityAdapter` (`src/neuri/adapters/antigravity.py`) mapping to real `agy` flags (`--print`, `--output-format stream-json`, `--mode auto`, `--prompt-interactive`, etc.).
- Implement Tier-1 `CodexAdapter` (`src/neuri/adapters/codex.py`) mapping to `codex exec --json` and interactive mode.
- Implement Tier-2 extensible adapters (`opencode.py`, `openclaw.py`, `ollama_local.py`) and `AdapterRegistry` factory (`registry.py`).

### R5. Pre-Flight Hook & DAG Orchestrator
- Implement `src/neuri/core/preflight.py` validating PHI sanitization (`phi_sanitized == True`), coordinate space alignment, and artifact existence at zero token cost.
- Implement `src/neuri/core/orchestrator.py` executing DAG nodes topologically with bounded auto-retry ($N=2$) attaching structured diagnostic feedback and transitioning to `WAITING_OPERATOR` upon exhaustion or breaker trip.

### R6. GUI-Ready Session Engine & Slash Commands
- Implement `src/neuri/core/slash_commands.py` handling `/init`, `/skills`, `/status`, `/harness`, `/retry`, `/cancel`, `/clear`, `/help`, `/exit`.
- Implement `src/neuri/core/session.py` (`NeuriSessionEngine`) as a UI-agnostic controller managing conversation turns, dispatching commands, running DAG orchestration, and publishing `SessionEvent` streams.

### R7. Interactive Terminal Chat UI (`neuri`) & CLI Entrypoint
- Implement `src/neuri/cli/main.py`: running `neuri` (no args) opens the interactive chat session; `neuri -p "<prompt>"` / `neuri --print "<prompt>"` executes headlessly.
- Implement `src/neuri/ui/terminal_chat.py` with Textual: workspace banner, scrollable chat canvas, collapsible `<thinking>` traces, inline DAG progress badges, bottom prompt input with slash-command autocompletion, and live token/cost status bar.

### R8. Universal Python Coding Standards (`python_standard.md`)
- Strict PEP 8 styling (snake_case, PascalCase, 4-space indent, 79–88 char line limit).
- Type hints on all function arguments, class methods, and return values.
- Mandatory custom docstring format on every class, method, and function.
- Single responsibility principle, single return variable/type, zero global variables.

## Verification Resources & Acceptance Criteria

### Verification Commands
```bash
# 1. Environment & Dependencies
uv sync --all-extras

# 2. Automated Test Suite
uv run pytest -v

# 3. Headless CLI Verification
uv run neuri -p "/skills"
uv run neuri -p "/status"
uv run neuri -p "Preprocess sub-01 anatomical scan" --dry-run
```

### Acceptance Criteria
- [ ] All unit and adapter tests pass via `uv run pytest -v` with zero failures.
- [ ] Running `uv run neuri -p "/skills"` renders the Tier-0 skills index cleanly.
- [ ] Running `uv run neuri -p "/init"` creates a valid `.neuri/` workspace (`neuri.toml`, `state.db`, `references.bib`, `execution_history.json`, `qa_snapshots/`).
- [ ] Deterministic NDJSON stream replay tests for `AntigravityAdapter` and `CodexAdapter` verify thinking stream extraction, token tallies, and circuit breakers without requiring live LLM API keys.
- [ ] All Python source files adhere strictly to PEP 8, full type annotations, no global variables, and the preferred docstring format.
- [ ] A copy of the approved plan is saved to `technical_documenation/PHASE_1_IMPLEMENTATION_PLAN.md` and `technical_documenation/NEURI_ARCHITECTURE_AND_IMPLEMENTATION_PLAN.md` reflects the interactive chat UX.

## 2026-10-25T19:34:53Z

The server has restarted and the user has instructed us to carry on with implementing phase1_implementation_plan.md. Please resume execution from your last checkpoint, check on the status of your worker/explorer subagents, and continue through the remaining milestones.
