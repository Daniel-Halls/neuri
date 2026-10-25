# E2E Test Infra: Neuri (Phase 1)

## Test Philosophy
- Opaque-box, requirement-driven. Derived from `ORIGINAL_REQUEST.md` and user-facing specs, independent of implementation internals.
- Verification methodology: Category-Partition + Boundary Value Analysis (BVA) + Pairwise Combinatorial Testing + Real-World Workload Testing.
- Progressive testability: Tier 1 tests give pass/fail signals with early milestones without depending on unbuilt downstream features.
- Zero-API-Cost & Offline: Uses deterministic NDJSON stream fixtures for `AntigravityAdapter` and `CodexAdapter` replay.

---

## Feature Inventory & Test Coverage
| # | Feature | Source (Requirement) | Tier 1 (Coverage) | Tier 2 (Boundary) | Tier 3 (Pairwise) |
|---|---------|----------------------|:-----------------:|:-----------------:|:-----------------:|
| 1 | ModalityType Enum | R1, Specs §4.1 | 5 | 5 | ✓ |
| 2 | SanitizedNeuroHeader (phi_sanitized: True) | R1, Specs §4.1 | 5 | 5 | ✓ |
| 3 | RemoteArtifact Schema | R1, Specs §4.1 | 5 | 5 | ✓ |
| 4 | TaskState & TaskNode Schemas | R1, Specs §4.1 | 5 | 5 | ✓ |
| 5 | TaskEdge & DAG Schemas | R1, Specs §4.2 | 5 | 5 | ✓ |
| 6 | NeuriTaskEnvelope & Result Schemas | R1, Specs §4.1 | 5 | 5 | ✓ |
| 7 | TelemetryEvent & NiiVue Schemas | R1, Specs §4.1 | 5 | 5 | ✓ |
| 8 | Two-Tier Config Loader (~/.neuri + .neuri) | R1, Specs §5.1 | 5 | 5 | ✓ |
| 9 | Workspace Initializer (.neuri/ workspace) | R1, R6, Specs §5.1 | 5 | 5 | ✓ |
| 10 | Tier-0 Compact Catalog (skills/index.yaml <300 tokens) | R1, Specs §3.5 | 5 | 5 | ✓ |
| 11 | SQLite WAL Blackboard (state.db, 7 tables) | R2, Specs §4.2 | 5 | 5 | ✓ |
| 12 | Blackboard Topological DAG (get_ready_nodes) | R2, Specs §3.2 | 5 | 5 | ✓ |
| 13 | Provenance Logging (execution_history.json) | R2, Specs §4.2 | 5 | 5 | ✓ |
| 14 | TelemetryTap Event Normalization | R3, Specs §3.1 | 5 | 5 | ✓ |
| 15 | Streaming <thinking> Tag Split-Parser | R3, Specs §3.1 | 5 | 5 | ✓ |
| 16 | Token & Cost Circuit Breakers | R3, Specs §7 | 5 | 5 | ✓ |
| 17 | Consecutive Identical Tool Failure Breaker | R3, Specs §7 | 5 | 5 | ✓ |
| 18 | BaseHarnessAdapter Protocol & Dual Mode | R4, Specs §3.1 | 5 | 5 | ✓ |
| 19 | Tier-1 AntigravityAdapter (agy flags) | R4, Specs §3.1 | 5 | 5 | ✓ |
| 20 | Tier-1 CodexAdapter (codex exec --json) | R4, Specs §3.1 | 5 | 5 | ✓ |
| 21 | Tier-2 Adapters (opencode, openclaw, ollama) | R4, Specs §3.1 | 5 | 5 | ✓ |
| 22 | AdapterRegistry Factory | R4, Specs §3.1 | 5 | 5 | ✓ |
| 23 | Deterministic Pre-Flight Gate (zero-token PHI & space) | R5, Specs §7 | 5 | 5 | ✓ |
| 24 | DAGOrchestrator Topological Execution | R5, Specs §3.2 | 5 | 5 | ✓ |
| 25 | Bounded Auto-Retry (N=2) & Feedback | R5, Specs §3.2 | 5 | 5 | ✓ |
| 26 | WAITING_OPERATOR Escalation | R5, Specs §3.2 | 5 | 5 | ✓ |
| 27 | Slash Command Registry & Handlers (9 commands) | R6, Specs §5.2 | 5 | 5 | ✓ |
| 28 | NeuriSessionEngine UI-Agnostic Stream | R6, Specs §1 | 5 | 5 | ✓ |
| 29 | Typer CLI Entrypoint (neuri, -p, --dry-run) | R7, Specs §5.2 | 5 | 5 | ✓ |
| 30 | Textual Terminal Chat UI App | R7, Specs §5.2 | 5 | 5 | ✓ |
| 31 | Universal Python Standards AST Compliance | R8, python_standard.md | 5 | 5 | ✓ |

---

## Test Architecture
- **Runner**: `pytest` executed with `-v` (e.g. `uv run pytest -v`).
- **Pass/Fail Semantics**: All tests must pass with exit code 0. Zero warnings treated as errors where configured.
- **Test Case Format**: Deterministic Python test files in `tests/` structured across:
  - `tests/unit/`: Component isolation tests.
  - `tests/adapters/`: Adapter tests using NDJSON fixtures.
  - `tests/e2e/`: End-to-end headless CLI and workspace lifecycle tests.
- **Fixtures Directory**: `tests/fixtures/` contains recorded NDJSON event streams for `agy` and `codex`.

---

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Complexity |
|---|----------|--------------------|------------|
| 1 | Full Workspace Lifecycle (`/init`, `/skills`, `/status`) | Two-Tier Config, Blackboard, Slash Commands, CLI | Medium |
| 2 | Anatomical Scan Preprocessing Dry-Run (`neuri -p "Preprocess sub-01 anatomical scan" --dry-run`) | Session Engine, DAG Orchestrator, Pre-flight Hook, CLI | High |
| 3 | Antigravity Stream Replay with Thinking & Token Counting | `AntigravityAdapter`, `TelemetryTap`, `<thinking>` Parser | High |
| 4 | Codex Stream Replay with Tool Failure Circuit Breaker Trip | `CodexAdapter`, `TelemetryTap`, Circuit Breakers, Orchestrator `WAITING_OPERATOR` | High |
| 5 | Multi-turn Session Conversation with Slash Commands (`/status`, `/harness`, `/retry`) | `NeuriSessionEngine`, Slash Command Registry, Blackboard DAG State | High |

---

## Coverage Thresholds
- **Tier 1**: $\ge 5$ test cases per feature (happy path isolation).
- **Tier 2**: $\ge 5$ test cases per feature (boundary values, invalid inputs, edge cases).
- **Tier 3**: Pairwise coverage of major feature interactions (e.g., config + blackboard, telemetry + circuit breakers, preflight + orchestrator).
- **Tier 4**: $\ge 5$ realistic end-to-end application scenarios.
- **AST Compliance**: Automated AST validator testing all `src/neuri/` files for strict adherence to `python_standard.md`.
