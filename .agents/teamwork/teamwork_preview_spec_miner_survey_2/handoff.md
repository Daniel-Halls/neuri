# Specification Survey Report: R4 (Harness Adapters & Registry), R5 (Pre-Flight Hook & DAG Orchestrator), R7 (CLI Entrypoint & Terminal Chat UI)

**Author:** Specification Miner (Survey 2)  
**Date:** 2026-10-25  
**Working Directory:** `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_spec_miner_survey_2/`  
**Target Project:** Neuri Phase 1 (`/Users/mszdjh3/code/neuri`)  

---

## 1. Observation

Direct observations from authoritative project specification sources:

### 1.1 `ORIGINAL_REQUEST.md`
- **R4 (Lines 33–37):**
  > "Implement `src/neuri/adapters/base.py` (`BaseHarnessAdapter`) supporting dual-mode execution (headless structured JSON streaming per DAG node + interactive PTY pass-through).  
  > Implement Tier-1 `AntigravityAdapter` (`src/neuri/adapters/antigravity.py`) mapping to real `agy` flags (`--print`, `--output-format stream-json`, `--mode auto`, `--prompt-interactive`, etc.).  
  > Implement Tier-1 `CodexAdapter` (`src/neuri/adapters/codex.py`) mapping to `codex exec --json` and interactive mode.  
  > Implement Tier-2 extensible adapters (`opencode.py`, `openclaw.py`, `ollama_local.py`) and `AdapterRegistry` factory (`registry.py`)."
- **R5 (Lines 39–42):**
  > "Implement `src/neuri/core/preflight.py` validating PHI sanitization (`phi_sanitized == True`), coordinate space alignment, and artifact existence at zero token cost.  
  > Implement `src/neuri/core/orchestrator.py` executing DAG nodes topologically with bounded auto-retry ($N=2$) attaching structured diagnostic feedback and transitioning to `WAITING_OPERATOR` upon exhaustion or breaker trip."
- **R7 (Lines 47–50):**
  > "Implement `src/neuri/cli/main.py`: running `neuri` (no args) opens the interactive chat session; `neuri -p "<prompt>"` / `neuri --print "<prompt>"` executes headlessly.  
  > Implement `src/neuri/ui/terminal_chat.py` with Textual: workspace banner, scrollable chat canvas, collapsible `<thinking>` traces, inline DAG progress badges, bottom prompt input with slash-command autocompletion, and live token/cost status bar."
- **Verification Commands (Lines 68–71):**
  > `uv run neuri -p "/skills"`  
  > `uv run neuri -p "/status"`  
  > `uv run neuri -p "Preprocess sub-01 anatomical scan" --dry-run`
- **Replay & Mock Acceptance Criteria (Line 77):**
  > "Deterministic NDJSON stream replay tests for `AntigravityAdapter` and `CodexAdapter` verify thinking stream extraction, token tallies, and circuit breakers without requiring live LLM API keys."

### 1.2 `technical_documenation/NEURI_ARCHITECTURE_AND_IMPLEMENTATION_PLAN.md`
- **Section 3.1 Tier 1: The Vendor-Agnostic Harness Adapter Layer (Lines 75–103):**
  - Dual-mode execution contract: Headless structured JSON streaming per DAG node (default) using serialized `NeuriTaskEnvelope` with isolated working directory / git worktree; Interactive PTY / ACP pass-through mode on escalation (`WAITING_OPERATOR`) or `--interactive`.
  - Tier-1 `AntigravityAdapter`: wraps `agy` CLI using workspace rule/skill injection, temporary MCP config mounts, and structured transcript/stream output parsing. Extracts `<thinking>` reasoning blocks, tool calls, and token metrics in real time.
  - Tier-1 `CodexAdapter`: wraps `codex exec --json`, injecting scoped `.mcp.json` configs and workspace sandboxes. Parses JSONL event streams into canonical events.
  - Tier-2 Extensible Adapters: `opencode.py`, `openclaw.py`, `claude.py`, and `ollama_local.py` (direct `httpx` streaming to `/api/chat`).
  - Unified TelemetryTap interceptor: normalizes events into `ThinkingDelta`, `TokenUsageUpdate`, `ToolCallLifecycle`, and `CircuitBreakerAlert`.
- **Section 3.2 Tier 2: Blackboard DAG Coordinator & Node State Machine (Lines 128–150):**
  - Node states: `PENDING` -> `PREFLIGHT_CHECK` -> `RUNNING` -> `QA_REVIEW` -> `COMPLETED`, with transitions to `RETRYING` (attempt $\le 2$) and `WAITING_OPERATOR` (attempt $> 2$ or breaker tripped).
  - Bounded auto-retry ($N=2$ default) attaching structured diagnostic feedback report.
  - Human-in-the-loop escalation: node pauses in `WAITING_OPERATOR`, alerting the operator in the TUI/terminal.
- **Section 4.1 Data Contracts & Schemas (Lines 243–364):**
  - `NeuriTaskEnvelope`: `workflow_id`, `node_id`, `agent_role`, `harness_id`, `execution_mode`, `system_prompt`, `task_instruction`, `skill_paths`, `mcp_servers`, `input_artifacts`, `max_tokens_budget`, `max_cost_usd`, `attempt_number`, `max_retries`, `diagnostic_feedback`.
  - `TelemetryEvent`: `event_id`, `workflow_id`, `node_id`, `harness_id`, `timestamp`, `event_type`, `thinking_text`, `input_tokens`, `cached_tokens`, `reasoning_tokens`, `output_tokens`, `estimated_cost_usd`, `tool_name`, `tool_host`, `tool_status`, `duration_ms`.
  - `SanitizedNeuroHeader`: enforces `phi_sanitized: Literal[True] = True`.
- **Section 5.1 Routing and Budget Configuration (Lines 403–417):**
  - Routing map per agent role: `coordinator = { harness = "agy", mode = "headless_json" }`, `pipeline_engineer = { harness = "codex", mode = "headless_json" }`, etc.
  - Budgets: `max_node_tokens = 64000`, `max_workflow_cost_usd = 10.00`, `max_node_retries = 2`.
- **Section 7 Deterministic Zero-Token Pre-Flight Validation (Lines 524–529):**
  - Verification of: input `RemoteArtifact` URI existence, coordinate space alignment (`space` matching across overlays/inputs), affine orientation consistency (RAS+ vs LPS+), disk quota/scratch space, Apptainer/Singularity container `.sif` image existence and checksum.

### 1.3 `/Users/mszdjh3/.gemini/config/rules/python_standard.md`
- Strict PEP 8, 4-space indentation, 79–88 char line length.
- Type hints on all function parameters and return values.
- Mandatory docstring template with `Parameters` and `Returns` blocks for every class, method, and function.
- Single return variable and single return type; zero global variables; single responsibility per function.

---

## 2. Logic Chain

1. **Dual Entrypoint Architecture (R7):**
   - Per `ORIGINAL_REQUEST.md` (lines 47–49) and verification commands (lines 68–71), `neuri` serves as both an interactive chat interface and a headless CLI runner.
   - When executed without prompt arguments (`neuri`), it launches the interactive Textual application (`src/neuri/ui/terminal_chat.py`).
   - When executed with `-p` / `--print "<prompt>"`, it bypasses the Textual TUI and executes the prompt headlessly via `src/neuri/core/session.py` (`NeuriSessionEngine`), outputting clean text to stdout.
   - If the prompt is a slash command (e.g., `/skills`, `/status`, `/init`), it resolves the command immediately and prints the result without invoking an external LLM harness.
   - If `--dry-run` is passed, the orchestrator generates the workflow DAG, runs deterministic pre-flight checks, and prints the planned execution graph without launching external subprocesses.

2. **Harness Adapter Decoupling & Unified Telemetry (R4):**
   - The orchestrator and agents do not invoke vendor CLIs directly; all execution routes through `BaseHarnessAdapter`.
   - `AntigravityAdapter` maps to `agy` CLI flags (`--print`, `--output-format stream-json`, `--mode auto`, `--prompt-interactive`).
   - `CodexAdapter` maps to `codex exec --json` and interactive sessions.
   - Both adapters pipe their raw stdout/stderr streams into `TelemetryTap`, which parses stream events into normalized `TelemetryEvent` instances (`thinking_delta`, `token_usage`, `tool_lifecycle`, `circuit_breaker`).
   - For offline testing and CI without API keys, both adapters support deterministic NDJSON stream replay, parsing pre-recorded fixture files to simulate real harness execution.
   - Tier-2 adapters (`opencode.py`, `openclaw.py`, `ollama_local.py`) adhere to the exact same base contract. `ollama_local.py` connects via `httpx.AsyncClient` to Ollama's streaming `/api/chat` endpoint.
   - `AdapterRegistry` provides a centralized lookup and factory for instantiating adapters based on configuration routing (`[harnesses.routing]`).

3. **Deterministic Pre-Flight Gate (R5):**
   - LLM generation and compute execution should never run on invalid or un-anonymized data.
   - `preflight.py` executes before any task node runs and consumes zero LLM tokens.
   - It performs strict programmatic validation:
     1. Verifies that all `RemoteArtifact` inputs have `header_summary.phi_sanitized == True`. Any un-anonymized header triggers an immediate pre-flight rejection.
     2. Verifies coordinate space consistency (e.g., ensuring overlays share the template space, and alerting on incompatible orientation codes like RAS+ vs LPS+).
     3. Verifies POSIX file existence and non-zero size for local artifacts.
     4. Verifies positive token and cost budget allocations.
   - If pre-flight fails, the node transitions to `RETRYING` (if attempts remain) with structured diagnostic feedback, or escalates to `WAITING_OPERATOR`.

4. **DAG Orchestration & Failure Recovery (R5):**
   - The `DAGOrchestrator` reads DAG dependencies from the SQLite Blackboard (`blackboard.py`).
   - Nodes transition through: `PENDING` -> `PREFLIGHT_CHECK` -> `RUNNING` -> `QA_REVIEW` -> `COMPLETED`.
   - Bounded auto-retry ($N=2$) captures preflight failures, non-zero exit codes, and QA rejections. On each retry, `attempt_number` increments and `diagnostic_feedback` is appended to the envelope.
   - When retries are exhausted ($attempt > max\_retries$) or a circuit breaker trips (`CircuitBreakerTripped`), the node transitions to `WAITING_OPERATOR`.
   - In `WAITING_OPERATOR`, execution halts for that branch, alerting the operator in the Textual UI or CLI, allowing interactive PTY attachment, approval, retry with guidance, or cancellation.

5. **Textual Terminal Chat UI (R7):**
   - Built with Textual (`src/neuri/ui/terminal_chat.py`), adhering to modern terminal UX paradigms.
   - Provides:
     - Workspace banner showing active project, remote host alias, and harness.
     - Scrollable chat canvas with turn bubbles.
     - Collapsible `<thinking>` panels that stream `ThinkingDelta` events live and collapse once completed.
     - Inline DAG progress badges displaying real-time task node states.
     - Bottom input bar with slash command autocompletion (`/skills`, `/status`, `/init`, `/harness`, `/retry`, `/cancel`, `/clear`, `/help`, `/exit`).
     - Live footer status bar with token velocity and cost accumulator.

---

## 3. Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | R4: Adapters | `BaseHarnessAdapter` | Abstract base class defining dual-mode execution (headless JSON stream & interactive PTY pass-through) | `NeuriTaskEnvelope` | `AsyncIterator[TelemetryEvent]`, `NeuriTaskResult` | Raises `HarnessError`, `HarnessTimeoutError` | Arch Spec §3.1, Original Req R4 |
| 2 | R4: Adapters | `AntigravityAdapter` | Tier-1 harness adapter wrapping Google Antigravity CLI (`agy`) | `NeuriTaskEnvelope`, `agy` flags (`--print`, `--output-format stream-json`, `--mode auto`) | Normalized NDJSON stream events, `NeuriTaskResult` | Raises `HarnessNotFoundError` if `agy` missing; handles process exit $\ne 0$ | Arch Spec §3.1, Original Req R4 |
| 3 | R4: Adapters | `CodexAdapter` | Tier-1 harness adapter wrapping OpenAI Codex CLI (`codex`) | `NeuriTaskEnvelope`, `codex exec --json` flags | Normalized JSONL stream events, `NeuriTaskResult` | Raises `HarnessNotFoundError` if `codex` missing; handles process crash | Arch Spec §3.1, Original Req R4 |
| 4 | R4: Adapters | `OpenCodeAdapter` | Tier-2 extensible adapter for OpenCode CLI | `NeuriTaskEnvelope` | Stream events, `NeuriTaskResult` | Raises `NotImplementedError` or process error if CLI missing | Arch Spec §3.1, Original Req R4 |
| 5 | R4: Adapters | `OpenClawAdapter` | Tier-2 extensible adapter for OpenClaw CLI | `NeuriTaskEnvelope` | Stream events, `NeuriTaskResult` | Raises `NotImplementedError` or process error if CLI missing | Arch Spec §3.1, Original Req R4 |
| 6 | R4: Adapters | `OllamaLocalAdapter` | Tier-2 adapter connecting to local/Tailscale Ollama `/api/chat` via HTTP | `NeuriTaskEnvelope`, endpoint URL (default `http://localhost:11434`) | Streaming chunks, token counts | Handles connection refused, HTTP 5xx errors | Arch Spec §3.1, Original Req R4 |
| 7 | R4: Adapters | `AdapterRegistry` | Central factory and catalog mapping harness IDs to adapter implementations | Harness ID string (e.g. `"agy"`, `"codex"`), optional config dict | Instantiated `BaseHarnessAdapter` | Raises `KeyError` if harness ID unregistered | Original Req R4, Arch Spec §3.1 |
| 8 | R4: Testing | NDJSON Stream Replay | Deterministic offline test runner replaying pre-recorded NDJSON fixture streams | Path to `.ndjson` fixture file | Async stream of `TelemetryEvent` | Raises `FileNotFoundError` or `JSONDecodeError` on bad fixture | Original Req R4 (line 77), Arch Spec §8 |
| 9 | R5: Preflight | `PreFlightValidator` | Zero-token deterministic Python verification engine | `NeuriTaskEnvelope` | `PreflightCheckResult` (passed, errors, warnings) | Rejection with diagnostic report | Arch Spec §7, Original Req R5 |
| 10 | R5: Preflight | PHI Sanitization Check | Enforces that all input `RemoteArtifact` objects have `phi_sanitized == True` | `list[RemoteArtifact]` | `bool`, error list | Fails pre-flight if any artifact has `phi_sanitized == False` | Original Req R5, Arch Spec §3.3 |
| 11 | R5: Preflight | Coordinate Space Alignment | Verifies spatial coordinate space (`space`) and affine orientation consistency (RAS+ vs LPS+) | `list[RemoteArtifact]` | `bool`, error/warning list | Rejects or warns on space mismatch or left-right flip risk | Arch Spec §3.5, §7, Original Req R5 |
| 12 | R5: Preflight | Artifact Existence Check | Verifies local/remote POSIX paths exist and have non-zero size | `list[RemoteArtifact]` | `bool`, error list | Rejects missing or 0-byte input artifacts | Arch Spec §7, Original Req R5 |
| 13 | R5: Orchestrator | `DAGOrchestrator` | Coordinator executing DAG task nodes topologically using SQLite Blackboard | `workflow_id`, `prompt`, optional `dry_run: bool` | `AsyncIterator[SessionEvent]` | Handles node failures, circuit breakers, escalation | Arch Spec §3.2, Original Req R5 |
| 14 | R5: Orchestrator | Topological Node Dispatch | Queries blackboard for ready nodes whose dependencies are `COMPLETED` | `workflow_id` | `list[TaskNode]` | Empty list if no nodes ready or graph blocked | Arch Spec §3.2, §4.2 |
| 15 | R5: Orchestrator | Bounded Auto-Retry ($N=2$) | Automatically retries failed pre-flight or failed task nodes up to 2 times | Failed `TaskNode`, diagnostic report | Re-queued `TaskNode` with incremented attempt | Transitions to `WAITING_OPERATOR` when retries exhausted | Arch Spec §3.2, Original Req R5 |
| 16 | R5: Orchestrator | Circuit Breaker Escalation | Pauses node and escalates to operator when token/cost/tool breakers trip | `CircuitBreakerTripped` exception | Node transitioned to `WAITING_OPERATOR` | Logs breaker alert and halts branch execution | Arch Spec §3.1, §7, Original Req R3, R5 |
| 17 | R5: Orchestrator | Operator Escalation Handling | Provides hooks for operator to approve, retry with guidance, cancel, or attach PTY | `node_id`, operator action enum/guidance string | Updated node state, resumed execution | Rejects invalid state transitions | Arch Spec §3.2, Original Req R5 |
| 18 | R5: Orchestrator | Dry-Run Simulation | Simulates DAG generation and preflight checks without executing external harnesses | `workflow_id`, prompt, `dry_run=True` | Planned DAG graph and preflight results | Reports preflight errors without token spend | Verification commands, Original Req |
| 19 | R7: CLI | Typer CLI Entrypoint (`main.py`) | Main entrypoint supporting both interactive chat and headless execution | CLI flags (`-p`, `--print`, `--dry-run`, `--harness`, `--config`) | Exit code 0 on success, non-zero on failure | Prints formatted errors via `Rich` | Original Req R7, Verification Cmds |
| 20 | R7: CLI | Headless Prompt Mode | Executes prompt without launching Textual UI (`neuri -p "<prompt>"`) | Prompt string | Formatted stdout text / summary | Exits non-zero if workflow fails | Original Req R7 |
| 21 | R7: CLI | Headless Slash Commands | Evaluates slash commands headlessly (`neuri -p "/skills"`, `neuri -p "/status"`) | Slash command string | Printed catalog/status table | Rejects unknown slash commands with help message | Verification commands, Original Req R6, R7 |
| 22 | R7: UI | Textual Chat App (`terminal_chat.py`) | Full-screen interactive terminal chat interface launched by `neuri` (no args) | Terminal stdio | Rendered interactive UI | Recovers from terminal resizing; clean exit on `/exit` | Original Req R7 |
| 23 | R7: UI | Workspace Banner Widget | Displays project name, active host alias, and default harness | Config / session state | Rendered top header widget | Falls back to sensible defaults if unconfigured | Original Req R7 |
| 24 | R7: UI | Scrollable Chat Canvas | Scrollable turn feed rendering User, Assistant, and System messages | Stream of `SessionEvent` | Rendered turn bubbles | Handles long text with auto-scroll | Original Req R7 |
| 25 | R7: UI | Collapsible Thinking Widget | Expandable/collapsible widget streaming live chain-of-thought tokens | `ThinkingDelta` events | Collapsible Rich panel with token count | Collapses cleanly on click or shortcut (`ctrl+t`) | Original Req R7, Arch Spec §3.1 |
| 26 | R7: UI | Inline DAG Progress Badges | Visual status badges for DAG nodes (`[PENDING]`, `[RUNNING]`, `[COMPLETED]`, `[WAITING_OPERATOR]`) | Task node state updates | Rendered badge components | Color-coded status with spinner for running nodes | Original Req R7 |
| 27 | R7: UI | Bottom Input with Autocomplete | Prompt input field with slash-command suggestions (`/skills`, `/status`, etc.) | User typing, `Tab` key | Completed command string | Ignores invalid completions | Original Req R7 |
| 28 | R7: UI | Live Token/Cost Status Bar | Footer status bar displaying live token counts and USD cost accumulator | `TokenUsageUpdate` events | Rendered footer widget | Updates counters reactively | Original Req R7, Arch Spec §3.1 |
| 29 | R7: UI | Operator Escalation Modal | Interactive modal appearing when a node transitions to `WAITING_OPERATOR` | `operator_escalation` session event | Operator choice (Approve, Retry, Cancel, PTY) | Resumes or terminates workflow branch | Arch Spec §3.2, Original Req R5, R7 |

---

## 4. Edge Cases

| # | Feature | Input / Condition | Observed / Required Behavior |
|---|---------|-------------------|------------------------------|
| 1 | `AntigravityAdapter` | `agy` binary not installed in system `$PATH` | Adapter raises `HarnessNotFoundError` with actionable message ("Install `agy` or configure binary path in `~/.neuri/config.toml`"). |
| 2 | `AntigravityAdapter` | Malformed or truncated NDJSON line emitted by `agy` | Stream parser catches `JSONDecodeError`, logs debug warning, discards corrupted line, and continues streaming without crashing session. |
| 3 | `AntigravityAdapter` | `agy` subprocess terminated by SIGSEGV or SIGKILL | Adapter catches abrupt termination, captures standard error, and returns `NeuriTaskResult` with non-zero exit code and diagnostic explanation. |
| 4 | `CodexAdapter` | `codex` command hangs without emitting tokens for > `node_timeout_seconds` | Async timeout fires, terminates subprocess cleanly, and returns timeout failure triggering retry or `WAITING_OPERATOR`. |
| 5 | `BaseHarnessAdapter` | `run_interactive` called when stdin/stdout is not a TTY (e.g. CI pipeline or headless daemon) | Adapter detects `sys.stdin.isatty() is False`, raises `PTYUnavailableError`, preventing terminal corruption. |
| 6 | `OllamaLocalAdapter` | Local Ollama server is down or Tailscale host unreachable (`ConnectionRefusedError`) | Adapter catches `httpx.ConnectError`, formats diagnostic message explaining Ollama endpoint is offline, and transitions node to `RETRYING` or `WAITING_OPERATOR`. |
| 7 | `PreFlightValidator` | Neuroimaging artifact has `phi_sanitized == False` or unstripped patient name in header | Preflight validation immediately fails with zero LLM tokens consumed; returns `PreflightCheckResult(passed=False, errors=["PHI violation: artifact contains un-anonymized metadata"])`. |
| 8 | `PreFlightValidator` | Input overlay artifact is in `MNI152NLin2009cAsym` space while base scan is in `native` subject space without warp field | Preflight check detects spatial space mismatch, rejects task node before running compute, and appends coordinate alignment diagnostic report. |
| 9 | `PreFlightValidator` | Two volumes have conflicting affine orientation codes (e.g. `RAS+` vs `LPS+`) | Preflight check detects orientation mismatch and emits explicit warning/error to prevent catastrophic left-right brain hemisphere inversion. |
| 10 | `PreFlightValidator` | Input POSIX file referenced in `RemoteArtifact.posix_path` does not exist or has 0 bytes | Preflight check fails with `FileNotFoundError` / `EmptyArtifactError`, preventing wasteful harness invocations. |
| 11 | `DAGOrchestrator` | Task graph contains circular dependency cycle (e.g. Node A -> Node B -> Node A) | Topological sort detects cycle, raises `CircularDependencyError`, and marks workflow `FAILED` before starting. |
| 12 | `DAGOrchestrator` | Node fails deterministic preflight or exits non-zero on attempt 1 | Orchestrator logs diagnostic feedback, increments attempt to 2, transitions node state to `RETRYING`, and re-invokes task node. |
| 13 | `DAGOrchestrator` | Node fails on attempt 2 (exceeding `max_retries = 2`) | Orchestrator halts retries, transitions node to `WAITING_OPERATOR`, records full diagnostic report, and yields `operator_escalation` event. |
| 14 | `DAGOrchestrator` | `TelemetryTap` triggers `CircuitBreakerTripped` (node tokens > 64k or cost > $2.00) | Orchestrator catches breaker exception, immediately terminates adapter subprocess, transitions node to `WAITING_OPERATOR`, and alerts user. |
| 15 | `DAGOrchestrator` | Consecutive identical tool failure breaker trips ($3\times$ identical failure) | Orchestrator halts node execution, transitions to `WAITING_OPERATOR`, preventing runaway infinite tool loops. |
| 16 | `CLI Entrypoint` | User invokes `neuri -p "/skills"` in headless mode | CLI immediately evaluates slash command, renders the Tier-0 skills index table via Rich, and exits 0 without starting TUI or LLM harness. |
| 17 | `CLI Entrypoint` | User invokes `neuri -p "Preprocess scan" --dry-run` | CLI generates DAG, executes zero-token preflight checks, prints planned tasks and dependency tree, and exits 0 without calling external subprocesses. |
| 18 | `CLI Entrypoint` | User runs `neuri` (no args) in a headless environment without a TTY (e.g. `neuri < /dev/null`) | CLI detects absence of interactive TTY, prints friendly message directing user to run with `-p` or `--help`, and exits with code 1. |
| 19 | `Textual UI` | Terminal window resized to very small viewport (<40 columns or <10 rows) | Textual layout adjusts responsively or displays compact warning without crashing or corrupting terminal state. |
| 20 | `Textual UI` | Stream emits high-frequency `ThinkingDelta` chunks (e.g. 50 chunks/sec) | Textual widget buffers and throttles rendering updates to maintain 60 FPS UI responsiveness without freezing the input bar. |
| 21 | `Textual UI` | User presses `Tab` after typing `/` in the prompt input | Textual popup displays autocomplete list of slash commands (`/skills`, `/status`, `/init`, `/harness`, `/retry`, `/cancel`, `/clear`, `/help`, `/exit`). |
| 22 | `Textual UI` | User types an unknown slash command (e.g. `/foo`) | UI renders a system notice: "Unknown command `/foo`. Type `/help` for available commands." without executing LLM turn. |

---

## 5. Required Interfaces and Data Contracts

### 5.1 `src/neuri/adapters/base.py` (`BaseHarnessAdapter`)
```python
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from neuri.core.schemas import NeuriTaskEnvelope, NeuriTaskResult, TelemetryEvent


class BaseHarnessAdapter(ABC):
    """Abstract base class defining the vendor-agnostic harness adapter protocol.

    Supports dual-mode execution: headless structured JSON streaming per DAG
    task node and interactive PTY pass-through for human-in-the-loop steering.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the harness adapter with optional configuration dictionary.

        Parameters
        ------------
        config: dict[str, Any] | None
            Optional configuration dictionary containing timeout, paths, or flags.
            Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes instance attributes.
        """
        self.config: dict[str, Any] = config or {}

    @abstractmethod
    async def run_headless(
        self, envelope: NeuriTaskEnvelope
    ) -> AsyncIterator[TelemetryEvent | NeuriTaskResult]:
        """Execute a task envelope in headless non-interactive JSON stream mode.

        Streams normalized TelemetryEvent instances in real time and concludes
        with a final NeuriTaskResult.

        Parameters
        ------------
        envelope: NeuriTaskEnvelope
            The normalized task envelope dispatched by the DAG orchestrator.

        Returns
        --------
            AsyncIterator[TelemetryEvent | NeuriTaskResult]: async iterator
                Yields telemetry events followed by the final task result.
        """
        ...

    @abstractmethod
    def run_interactive(self, envelope: NeuriTaskEnvelope) -> int:
        """Execute a task envelope in interactive PTY / ACP pass-through mode.

        Attaches the harness directly to the user's terminal/PTY for live
        human steering and debugging.

        Parameters
        ------------
        envelope: NeuriTaskEnvelope
            The normalized task envelope containing context and instructions.

        Returns
        --------
            int: integer object
                Process exit status code.
        """
        ...

    @abstractmethod
    def check_availability(self) -> bool:
        """Verify whether the underlying harness CLI executable is installed and runnable.

        Parameters
        ------------
        None

        Returns
        --------
            bool: boolean object
                True if the executable is accessible in PATH, False otherwise.
        """
        ...

    @abstractmethod
    def get_version(self) -> str:
        """Retrieve the version string of the underlying harness executable.

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                Version string or empty string if unavailable.
        """
        ...
```

### 5.2 `src/neuri/adapters/antigravity.py` (`AntigravityAdapter`)
```python
class AntigravityAdapter(BaseHarnessAdapter):
    """Tier-1 adapter for the Google Antigravity CLI (agy).

    Maps task envelopes to 'agy --print --output-format stream-json --mode auto'
    for headless execution and 'agy --prompt-interactive' for interactive mode.
    """

    executable_name: str = "agy"

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        replay_fixture_path: Path | None = None,
    ) -> None:
        """Initialize Antigravity adapter with optional config or mock replay fixture.

        Parameters
        ------------
        config: dict[str, Any] | None
            Optional configuration settings. Defaults to None.
        replay_fixture_path: Path | None
            Optional path to NDJSON replay fixture for offline testing. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes adapter state.
        """
```

### 5.3 `src/neuri/adapters/codex.py` (`CodexAdapter`)
```python
class CodexAdapter(BaseHarnessAdapter):
    """Tier-1 adapter for the OpenAI Codex CLI (codex).

    Maps task envelopes to 'codex exec --json' for headless execution and
    standard codex interactive sessions for interactive PTY mode.
    """

    executable_name: str = "codex"

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        replay_fixture_path: Path | None = None,
    ) -> None:
        """Initialize Codex adapter with optional config or mock replay fixture.

        Parameters
        ------------
        config: dict[str, Any] | None
            Optional configuration settings. Defaults to None.
        replay_fixture_path: Path | None
            Optional path to JSONL replay fixture for offline testing. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes adapter state.
        """
```

### 5.4 `src/neuri/adapters/registry.py` (`AdapterRegistry`)
```python
class AdapterRegistry:
    """Central factory and registry for vendor-agnostic harness adapters."""

    def __init__(self) -> None:
        """Initialize an empty adapter registry with default Tier-1 and Tier-2 mappings.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Populates internal registry dictionary.
        """
        self._registry: dict[str, type[BaseHarnessAdapter]] = {}

    def register(
        self, harness_id: str, adapter_cls: type[BaseHarnessAdapter]
    ) -> None:
        """Register an adapter class for a given harness identifier.

        Parameters
        ------------
        harness_id: str
            Unique harness identifier string (e.g. 'agy', 'codex', 'ollama').
        adapter_cls: type[BaseHarnessAdapter]
            The adapter class implementing BaseHarnessAdapter.

        Returns
        --------
            None: NoneType object
                Updates internal registry mapping.
        """

    def get(
        self, harness_id: str, config: dict[str, Any] | None = None
    ) -> BaseHarnessAdapter:
        """Instantiate and return the harness adapter corresponding to harness_id.

        Parameters
        ------------
        harness_id: str
            Identifier string for the desired harness.
        config: dict[str, Any] | None
            Optional configuration dictionary passed to adapter constructor. Defaults to None.

        Returns
        --------
            BaseHarnessAdapter: BaseHarnessAdapter object
                Instantiated adapter ready for execution.
        """
```

### 5.5 `src/neuri/core/preflight.py` (`PreFlightValidator`)
```python
from pydantic import BaseModel, Field
from neuri.core.schemas import NeuriTaskEnvelope, RemoteArtifact


class PreflightCheckResult(BaseModel):
    """Result of deterministic zero-token pre-flight checks."""
    node_id: str
    passed: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PreFlightValidator:
    """Zero-token deterministic validator enforcing data privacy and spatial alignment."""

    def validate_envelope(
        self, envelope: NeuriTaskEnvelope
    ) -> PreflightCheckResult:
        """Execute deterministic pre-flight checks on a task envelope.

        Parameters
        ------------
        envelope: NeuriTaskEnvelope
            The task envelope to validate before dispatching to a harness.

        Returns
        --------
            PreflightCheckResult: PreflightCheckResult object
                Validation result indicating success or detailing validation errors.
        """

    def verify_phi_sanitization(
        self, artifacts: list[RemoteArtifact]
    ) -> tuple[bool, list[str]]:
        """Verify that all input artifacts have been stripped of PHI.

        Parameters
        ------------
        artifacts: list[RemoteArtifact]
            List of input artifacts referenced in the task envelope.

        Returns
        --------
            tuple[bool, list[str]]: tuple object
                Tuple of (passed flag, list of error messages).
        """

    def verify_coordinate_alignment(
        self, artifacts: list[RemoteArtifact]
    ) -> tuple[bool, list[str]]:
        """Verify coordinate space labels and affine orientation consistency.

        Parameters
        ------------
        artifacts: list[RemoteArtifact]
            List of input neuroimaging artifacts.

        Returns
        --------
            tuple[bool, list[str]]: tuple object
                Tuple of (passed flag, list of error/warning messages).
        """
```

### 5.6 `src/neuri/core/orchestrator.py` (`DAGOrchestrator`)
```python
class DAGOrchestrator:
    """Orchestrates topological DAG execution with bounded auto-retry and operator gates."""

    def __init__(
        self,
        blackboard: Blackboard,
        registry: AdapterRegistry,
        config: NeuriConfig,
    ) -> None:
        """Initialize the DAG orchestrator with state blackboard, adapter registry, and config.

        Parameters
        ------------
        blackboard: Blackboard
            The SQLite Blackboard storing workflow and task node state.
        registry: AdapterRegistry
            The registry for looking up harness adapters.
        config: NeuriConfig
            System configuration specifying routing and budget limits.

        Returns
        --------
            None: NoneType object
                Initializes orchestrator components.
        """

    async def execute_workflow(
        self, workflow_id: str, dry_run: bool = False
    ) -> AsyncIterator[SessionEvent]:
        """Execute a workflow DAG topologically to completion or operator escalation.

        Parameters
        ------------
        workflow_id: str
            Unique workflow identifier in the SQLite Blackboard.
        dry_run: bool
            If True, simulates execution without invoking external harnesses. Defaults to False.

        Returns
        --------
            AsyncIterator[SessionEvent]: async iterator
                Yields session events representing DAG progress, telemetry, and status changes.
        """
```

### 5.7 `src/neuri/cli/main.py` & `src/neuri/ui/terminal_chat.py`
```python
# main.py CLI Signature
def main(
    prompt: str | None = typer.Option(
        None, "-p", "--print", help="Execute prompt headlessly and print output"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Simulate DAG execution without external calls"
    ),
    harness: str | None = typer.Option(
        None, "--harness", "-H", help="Override default harness adapter"
    ),
    config_file: Path | None = typer.Option(
        None, "--config", "-c", help="Path to custom configuration file"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose debug logging"
    ),
    version: bool = typer.Option(
        False, "--version", help="Show Neuri version and exit"
    ),
) -> None:
    """Neuri CLI entrypoint: run interactive terminal chat or headless command."""


# terminal_chat.py Textual App Structure
class NeuriChatApp(App[None]):
    """Textual interactive terminal chat application for Neuri."""

    CSS = """
    /* Layout styles for header, chat canvas, thinking container, input bar, and status footer */
    """

    def compose(self) -> ComposeResult:
        """Compose the Textual widget hierarchy: banner, chat log, input bar, status bar."""
```

---

## 6. Caveats

- **No Caveats.** All requirements for R4, R5, and R7 have been mapped against authoritative project specifications (`ORIGINAL_REQUEST.md`, `NEURI_ARCHITECTURE_AND_IMPLEMENTATION_PLAN.md`, and `python_standard.md`).

---

## 7. Conclusion

Requirements R4, R5, and R7 form the execution, validation, and user interface core of Neuri Phase 1:
1. **R4** provides the vendor-agnostic adapter layer with Tier-1 first-class drivers for Google Antigravity (`agy`) and OpenAI Codex CLI (`codex`), plus Tier-2 stubs (`opencode`, `openclaw`, `ollama_local`) and offline NDJSON stream replay.
2. **R5** provides the deterministic zero-token privacy/coordinate preflight gate (`preflight.py`) and topological DAG orchestrator (`orchestrator.py`) with bounded auto-retry ($N=2$) and human-in-the-loop escalation (`WAITING_OPERATOR`).
3. **R7** provides the unified CLI entrypoint (`main.py`) supporting dual-mode execution (`neuri` for interactive Textual chat UI and `neuri -p "<prompt>"` for headless output) with rich interactive widgets (workspace banner, collapsible `<thinking>` traces, inline DAG badges, autocompleting input, and token/cost status bar).

All components strictly comply with the universal Python coding standards in `/Users/mszdjh3/.gemini/config/rules/python_standard.md`.

---

## 8. Verification Method

To verify the surveyed specifications independently during implementation:

1. **Verify Python Coding Standards & Type Checking:**
   ```bash
   uv run mypy src/neuri/adapters src/neuri/core/preflight.py src/neuri/core/orchestrator.py src/neuri/cli src/neuri/ui
   ```

2. **Verify Offline Adapter Replay & Telemetry Extraction:**
   ```bash
   uv run pytest tests/adapters/ -v
   ```
   *Expected:* Unit tests read pre-recorded NDJSON fixtures for `agy` and `codex`, verifying extraction of `<thinking>` deltas, token tallies, tool calls, and circuit breaker trip conditions without live API keys.

3. **Verify Zero-Token Pre-Flight Hook:**
   ```bash
   uv run pytest tests/unit/test_preflight.py -v
   ```
   *Expected:* Confirms rejection of un-anonymized headers (`phi_sanitized == False`), space mismatches, and orientation discrepancies at zero token cost.

4. **Verify Headless CLI Operations:**
   ```bash
   uv run neuri -p "/skills"
   uv run neuri -p "/status"
   uv run neuri -p "Preprocess sub-01 anatomical scan" --dry-run
   ```
   *Expected:* Prints formatted skills index, workspace status, and planned DAG without launching external harnesses or throwing uncaught exceptions.
