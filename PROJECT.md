# Project: Neuri (Phase 1)

## Architecture
Neuri is a vendor-agnostic neuroscience meta-harness.
Phase 1 architecture comprises:
1. **Core Data Contracts & Configuration**: Strict Pydantic v2 schemas (`SanitizedNeuroHeader` enforcing `phi_sanitized: Literal[True]`, `RemoteArtifact`, `TaskNode`, etc.), two-tier TOML configuration (`~/.neuri/config.toml` merged with `.neuri/neuri.toml`), and Tier-0 compact skill catalog (`skills/index.yaml` <300 tokens).
2. **SQLite WAL Blackboard & Provenance**: Persistent blackboard at `.neuri/state.db` in SQLite `WAL` mode managing 7 core relational tables, atomic transactions, topological dependency queries (`get_ready_nodes`), and immutable provenance logging (`.neuri/execution_history.json`).
3. **Unified TelemetryTap & Circuit Breakers**: Stream interceptor normalizing chunked tokens, parsing `<thinking>` tags across chunk boundaries, tracking tool call lifecycles, and enforcing hard resource guardrails (`max_node_tokens`, `max_workflow_cost_usd`, and 3 consecutive identical tool failures).
4. **Vendor-Agnostic Harness Adapter Layer**: Protocol-based adapter layer (`BaseHarnessAdapter`) supporting headless structured JSON streaming and interactive pass-through, Tier-1 drivers for Antigravity (`agy`) and OpenAI Codex (`codex`), Tier-2 stubs (`opencode`, `openclaw`, `ollama_local`), `AdapterRegistry`, and offline deterministic NDJSON stream replay testing.
5. **Pre-Flight Hook & DAG Orchestrator**: Zero-token deterministic pre-flight validator enforcing PHI sanitization, coordinate space consistency, and artifact existence; paired with `DAGOrchestrator` executing DAG nodes topologically with bounded auto-retry ($N=2$), diagnostic feedback, and `WAITING_OPERATOR` escalation.
6. **GUI-Ready Session Engine, Slash Commands, CLI & Textual TUI**: UI-agnostic `NeuriSessionEngine` streaming typed `SessionEvent`s, slash command registry (9 commands), unified Typer CLI entrypoint (`neuri`, `-p`, `--dry-run`), and Textual terminal chat application with collapsible reasoning and live telemetry.
7. **Quality, Standards & E2E Verification**: 100% adherence to Universal Python Standards (`python_standard.md`), comprehensive 5-tier test suite, and requirement verification.

---

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | `ModalityType` Enum | 12 supported neuroscience data modalities | M1 | Survey 1 |
| 2 | `SanitizedNeuroHeader` | PHI-sanitized structural metadata with `phi_sanitized: Literal[True]` | M1 | Survey 1 |
| 3 | `RemoteArtifact` | Pointer contract for remote neuro datasets & outputs | M1 | Survey 1 |
| 4 | `TaskState` Enum | State machine enum for DAG node execution lifecycle | M1 | Survey 1 |
| 5 | `TaskNode` | Specification of an executable step in Blackboard DAG | M1 | Survey 1 |
| 6 | `TaskEdge` | Directed dependency relationship between nodes | M1 | Survey 1 |
| 7 | `NeuriTaskEnvelope` | Task payload dispatched to `BaseHarnessAdapter` | M1 | Survey 1 |
| 8 | `NeuriTaskResult` | Structured execution result returned from harness | M1 | Survey 1 |
| 9 | `TelemetryEvent` | Canonical telemetry event emitted by `TelemetryTap` | M1 | Survey 1 |
| 10 | `NiiVueLayerSpec` | Spec for visual volume or surface layer overlay | M1 | Survey 1 |
| 11 | `NiiVueSceneSpec` | Declarative 3D/multiplanar scene manifest | M1 | Survey 1 |
| 12 | `ChatRole` & `ChatTurn` | Chat history models for user/assistant/operator | M1 | Survey 1 |
| 13 | `SessionEvent` | Event stream model emitted by `NeuriSessionEngine` | M1 | Survey 1 |
| 14 | Two-Tier Config Loader | Deep merge of `~/.neuri/config.toml` & `.neuri/neuri.toml` | M1 | Survey 1 |
| 15 | Workspace Initializer | Scaffolds `.neuri/` project workspace and template files | M1 | Survey 1 |
| 16 | Compact Catalog (`skills/index.yaml`) | Tier-0 compact catalog (<300 tokens) indexing 7 neuro skills | M1 | Survey 1 |
| 17 | `pyproject.toml` Scaffolding | Packaging via uv/hatchling with Python >=3.12 & dependencies | M1 | Survey 3 |
| 18 | SQLite WAL Blackboard Init | Creates `.neuri/state.db` in SQLite WAL mode | M2 | Survey 1 |
| 19 | Workflows Table & CRUD | Create, read, and update workflows in `workflows` table | M2 | Survey 1 |
| 20 | Task Nodes Table & CRUD | Create, read, update, state transition for task nodes | M2 | Survey 1 |
| 21 | Task Edges Table & CRUD | Add dependency edge between parent and child nodes | M2 | Survey 1 |
| 22 | Topological Ready Node Query | `get_ready_nodes()` returns unblocked nodes whose parents are `COMPLETED` | M2 | Survey 1 |
| 23 | Artifact Registration | Registers `RemoteArtifact` in `remote_artifacts` table | M2 | Survey 1 |
| 24 | Remote Job Tracking | Registers and updates Slurm/tmux asynchronous job status | M2 | Survey 1 |
| 25 | Citations Ledger | Registers verified BibTeX/DOI records in `citations_ledger` | M2 | Survey 1 |
| 26 | Provenance Store & History Export | Exports provenance DAG to `.neuri/execution_history.json` | M2 | Survey 1 |
| 27 | Unified TelemetryTap | Stream interceptor normalizing chunked tokens & tool calls | M3 | Survey 1 |
| 28 | Streaming `<thinking>` Parser | Streaming parser extracting `<thinking>` across chunk splits | M3 | Survey 1 |
| 29 | Max Node Tokens Breaker | Trips `CircuitBreakerTripped` if node exceeds token budget | M3 | Survey 1 |
| 30 | Max Workflow Cost Breaker | Trips `CircuitBreakerTripped` if workflow exceeds cost budget | M3 | Survey 1 |
| 31 | Consecutive Tool Failure Breaker | Trips `CircuitBreakerTripped` on 3 consecutive identical tool failures | M3 | Survey 1 |
| 32 | `BaseHarnessAdapter` Protocol | Abstract base adapter defining dual-mode execution contract | M4 | Survey 2 |
| 33 | Dual-Mode Execution Contract | Headless structured JSON streaming vs interactive PTY pass-through | M4 | Survey 2 |
| 34 | Tier-1 `AntigravityAdapter` | Maps to real `agy` CLI flags (`--print`, `--output-format stream-json`, etc.) | M4 | Survey 2 |
| 35 | Tier-1 `CodexAdapter` | Maps to `codex exec --json` and interactive mode | M4 | Survey 2 |
| 36 | Tier-2 `OpenCodeAdapter` Stub | Extensible stub for OpenCode harness | M4 | Survey 2 |
| 37 | Tier-2 `OpenClawAdapter` Stub | Extensible stub for OpenClaw harness | M4 | Survey 2 |
| 38 | Tier-2 `OllamaAdapter` | Direct HTTP streaming to Ollama `/api/chat` via `httpx` | M4 | Survey 2 |
| 39 | `AdapterRegistry` Factory | Central lookup and factory for instantiating harness adapters | M4 | Survey 2 |
| 40 | NDJSON Stream Replay Harness | Deterministic stream replay for offline testing without API keys | M4 | Survey 2, 3 |
| 41 | Deterministic Pre-Flight Gate | Zero-token validation gate before task node execution | M5 | Survey 2 |
| 42 | PHI Sanitization Check | Enforces `header_summary.phi_sanitized == True` | M5 | Survey 2 |
| 43 | Coordinate Space Alignment Check | Verifies template space match & orientation consistency | M5 | Survey 2 |
| 44 | Artifact Existence Validator | Verifies POSIX file existence and non-zero size for local artifacts | M5 | Survey 2 |
| 45 | Budget Allocation Validator | Verifies positive token and cost budget allocations | M5 | Survey 2 |
| 46 | `DAGOrchestrator` Engine | Executes DAG nodes topologically with state transitions | M5 | Survey 2 |
| 47 | Bounded Auto-Retry ($N=2$) | Retries failed nodes up to 2 times with diagnostic feedback | M5 | Survey 2 |
| 48 | `WAITING_OPERATOR` Escalation | Escalates to human operator upon retry exhaustion or breaker trip | M5 | Survey 2 |
| 49 | Slash Command Registry | Dispatches user input starting with `/` to registered handlers | M6 | Survey 1 |
| 50 | `/init` Slash Command Handler | Initializes current directory as Neuri project workspace | M6 | Survey 1 |
| 51 | `/skills` Slash Command Handler | Displays formatted catalog of Tier-0 neuroscience skills | M6 | Survey 1 |
| 52 | `/status` Slash Command Handler | Reports active workflow, DAG node states, tokens, and cost | M6 | Survey 1 |
| 53 | `/harness` Slash Command Handler | Displays current routing or switches active harness backend | M6 | Survey 1 |
| 54 | `/retry` Slash Command Handler | Re-triggers a failed or `WAITING_OPERATOR` node with feedback | M6 | Survey 1 |
| 55 | `/cancel` Slash Command Handler | Cancels running workflow or specific node | M6 | Survey 1 |
| 56 | `/clear` Slash Command Handler | Clears session conversation history buffer | M6 | Survey 1 |
| 57 | `/help` Slash Command Handler | Displays help menu with all available slash commands | M6 | Survey 1 |
| 58 | `/exit` Slash Command Handler | Signals session termination | M6 | Survey 1 |
| 59 | `NeuriSessionEngine` Controller | UI-agnostic conversation and execution controller | M6 | Survey 1 |
| 60 | Typer CLI Entrypoint (`main.py`) | Running `neuri` (no args) opens chat; `-p` executes headlessly | M6 | Survey 2 |
| 61 | Headless CLI Evaluation | `neuri -p "<prompt>"` / `neuri --print "<prompt>"` | M6 | Survey 2 |
| 62 | Dry-Run Planning Flag | `neuri -p "..." --dry-run` prints DAG plan without executing | M6 | Survey 2 |
| 63 | Interactive Textual Chat UI | Textual TUI app in `src/neuri/ui/terminal_chat.py` | M6 | Survey 2 |
| 64 | Textual Workspace Banner | Shows active project, remote host alias, and harness | M6 | Survey 2 |
| 65 | Textual Scrollable Chat Canvas | Scrollable turn-by-turn conversation canvas | M6 | Survey 2 |
| 66 | Textual Collapsible Thinking Accordion | Live collapsible container for `<thinking>` traces | M6 | Survey 2 |
| 67 | Textual Inline DAG Progress Badges | Visual badge widgets showing DAG node statuses | M6 | Survey 2 |
| 68 | Textual Prompt Autocompletion | Bottom prompt input with `/` autocompletion popup | M6 | Survey 2 |
| 69 | Textual Live Status Bar | Bottom status bar showing token count and cost tallies | M6 | Survey 2 |
| 70 | Python Standards AST Compliance Checker | AST-based checker asserting PEP 8, types, docstrings, 0 globals | M7 | Survey 3 |
| 71 | 100% E2E Test Suite Pass | Verifies all test tiers (Tiers 1-4) pass with exit code 0 | M7 | Survey 3 |
| 72 | Adversarial Coverage Hardening (Tier 5) | White-box adversarial testing with Challenger | M7 | Survey 3 |
| 73 | Documentation Sync | Syncs approved plan to `technical_documenation/` | M7 | Survey 3 |

---

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Package Scaffolding, Schemas, Two-Tier Config & Compact Catalog | `pyproject.toml`, `schemas.py`, `config.py`, `skills/index.yaml`, unit tests | none | DONE |
| M2 | SQLite WAL Blackboard & Provenance Store | `blackboard.py`, 7 tables, atomic CRUD, topological DAG query, provenance export, unit tests | M1 | PLANNED |
| M3 | Unified TelemetryTap & Circuit Breakers | `telemetry.py`, event normalization, `<thinking>` parser, 3 breaker policies, unit tests | M1 | PLANNED |
| M4 | Vendor-Agnostic Harness Adapter Layer & Stream Replay | `adapters/` (`base.py`, `antigravity.py`, `codex.py`, Tier-2 stubs, `registry.py`), NDJSON replay fixtures, adapter tests | M1, M3 | PLANNED |
| M5 | Pre-Flight Hook & DAG Orchestrator | `preflight.py`, `orchestrator.py`, zero-token validation, topological DAG execution, retry N=2, operator escalation, unit tests | M1, M2, M3, M4 | PLANNED |
| M6 | Slash Commands, GUI-Ready Session Engine, CLI & Textual UI | `slash_commands.py`, `session.py`, `main.py`, `terminal_chat.py`, CLI tests, headless tests | M1, M2, M3, M4, M5 | PLANNED |
| M7 | Final E2E Test Pass, Adversarial Hardening (Tier 5) & Plan Sync | 100% E2E test suite pass, AST standards checker, Tier 5 hardening, documentation sync | M1, M2, M3, M4, M5, M6, E2E-Track | PLANNED |

---

## Interface Contracts

### M1 (Schemas) ↔ All Modules
- `SanitizedNeuroHeader`: enforces `phi_sanitized: Literal[True] = True`
- `RemoteArtifact`: `uri: str` (`<host>:///<posix_path>`), `modality: ModalityType`, `space: str | None`, `header_summary: SanitizedNeuroHeader`
- `TaskState`: Enum(`PENDING`, `PREFLIGHT_CHECK`, `RUNNING`, `QA_REVIEW`, `COMPLETED`, `FAILED`, `CANCELLED`, `WAITING_OPERATOR`, `RETRYING`)
- `TaskNode`: `node_id: str`, `workflow_id: str`, `role: str`, `harness: str`, `state: TaskState`, `envelope: NeuriTaskEnvelope`, `diagnostic_feedback: list[str]`
- `NeuriTaskEnvelope`: `workflow_id: str`, `node_id: str`, `role: str`, `harness: str`, `task_instruction: str`, `input_artifacts: list[RemoteArtifact]`, `max_tokens_budget: int = 64000`, `max_cost_usd: float = 10.00`, `attempt_number: int = 1`, `max_retries: int = 2`
- `NeuriTaskResult`: `node_id: str`, `success: bool`, `exit_code: int`, `summary: str`, `output_artifacts: list[RemoteArtifact]`, `tokens_consumed: int`, `cost_usd: float`
- `TelemetryEvent`: `event_id: str`, `workflow_id: str`, `node_id: str`, `event_type: str`, `thinking_text: str | None`, `input_tokens: int = 0`, `output_tokens: int = 0`, `estimated_cost_usd: float = 0.0`
- `SessionEvent`: `event_id: str`, `session_id: str`, `event_type: str`, `timestamp: datetime`, `payload: dict[str, Any]`

### M2 (Blackboard) ↔ M5 (Orchestrator)
- `Blackboard.get_ready_nodes(workflow_id: str) -> list[TaskNode]`
- `Blackboard.update_node_state(node_id: str, state: TaskState, diagnostic_feedback: str | None = None) -> None`
- `Blackboard.register_artifact(artifact: RemoteArtifact, workflow_id: str) -> None`
- `Blackboard.export_provenance(workflow_id: str, output_path: Path) -> dict[str, Any]`

### M3 (TelemetryTap) ↔ M4 (Adapters) & M5 (Orchestrator)
- `TelemetryTap.process_chunk(chunk: str) -> list[TelemetryEvent]`
- `TelemetryTap.record_tool_call(tool_name: str, success: bool) -> None`
- Raises `CircuitBreakerTripped(reason: str, node_id: str)` when `max_node_tokens`, `max_workflow_cost_usd`, or 3 consecutive identical tool failures occur.

### M4 (Adapters) ↔ M5 (Orchestrator)
- `BaseHarnessAdapter.execute_headless(envelope: NeuriTaskEnvelope) -> AsyncIterator[TelemetryEvent]`
- `BaseHarnessAdapter.get_result() -> NeuriTaskResult`
- `AdapterRegistry.get_adapter(harness_id: str) -> BaseHarnessAdapter`

### M5 (Preflight) ↔ M5 (Orchestrator)
- `PreFlightValidator.validate(node: TaskNode) -> tuple[bool, str | None]` (zero-token validation)

### M6 (Session Engine) ↔ UI / CLI
- `NeuriSessionEngine.process_input(text: str) -> AsyncIterator[SessionEvent]`
- `SlashCommandRegistry.dispatch(command_line: str) -> SlashCommandResult`

---

## Code Layout
```
/Users/mszdjh3/code/neuri/
├── pyproject.toml
├── README.md
├── LICENSE
├── technical_documenation/
│   ├── NEURI_ARCHITECTURE_AND_IMPLEMENTATION_PLAN.md
│   └── PHASE_1_IMPLEMENTATION_PLAN.md
├── skills/
│   └── index.yaml
├── src/
│   └── neuri/
│       ├── __init__.py
│       ├── cli/
│       │   ├── __init__.py
│       │   └── main.py
│       ├── ui/
│       │   ├── __init__.py
│       │   └── terminal_chat.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── schemas.py
│       │   ├── config.py
│       │   ├── blackboard.py
│       │   ├── telemetry.py
│       │   ├── preflight.py
│       │   ├── orchestrator.py
│       │   ├── slash_commands.py
│       │   └── session.py
│       └── adapters/
│           ├── __init__.py
│           ├── base.py
│           ├── antigravity.py
│           ├── codex.py
│           ├── opencode.py
│           ├── openclaw.py
│           ├── ollama_local.py
│           └── registry.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── fixtures/
    │   ├── agy_stream_sample.ndjson
    │   ├── agy_breaker_sample.ndjson
    │   ├── codex_stream_sample.ndjson
    │   └── codex_error_sample.ndjson
    ├── unit/
    │   ├── test_schemas.py
    │   ├── test_config.py
    │   ├── test_blackboard.py
    │   ├── test_telemetry.py
    │   ├── test_preflight.py
    │   ├── test_orchestrator.py
    │   ├── test_slash_commands.py
    │   ├── test_session.py
    │   └── test_standards_compliance.py
    ├── adapters/
    │   ├── test_base_adapter.py
    │   ├── test_antigravity_adapter.py
    │   ├── test_codex_adapter.py
    │   └── test_registry.py
    └── e2e/
        ├── test_cli_headless.py
        └── test_workspace_init.py
```
