# Handoff Report: Core Schemas Specification (M1-2)

**Agent Role**: Explorer M1-2  
**Working Directory**: `/Users/mszdjh3/code/neuri/.agents/teamwork/teamwork_preview_explorer_m1_2/`  
**Date**: 2026-10-25  

---

## 1. Observation

Direct observations from authoritative specifications and codebase:

1. **ORIGINAL_REQUEST.md (Lines 18–21, 51–56):**
   > "Implement `src/neuri/core/schemas.py` defining strict Pydantic models: `ModalityType`, `SanitizedNeuroHeader` (enforcing `phi_sanitized: Literal[True]`), `RemoteArtifact`, `TaskState`, `TaskNode`, `TaskEdge`, `NeuriTaskEnvelope`, `NeuriTaskResult`, `TelemetryEvent`, `NiiVueLayerSpec`, `NiiVueSceneSpec`, `ChatRole`, `ChatTurn`, and `SessionEvent`."
   > "Strict PEP 8 styling (snake_case, PascalCase, 4-space indent, 79–88 char line limit). Type hints on all function arguments, class methods, and return values. Mandatory custom docstring format on every class, method, and function. Single responsibility principle, single return variable/type, zero global variables."

2. **technical_documenation/NEURI_ARCHITECTURE_AND_IMPLEMENTATION_PLAN.md (Lines 240–364):**
   - Section 4.1 defines the canonical Pydantic models:
     - `ModalityType`: 12 canonical modalities (`T1w`, `T2w`, `bold`, `dwi`, `tractography`, `surface`, `eeg`, `meg`, `ieeg`, `posterior`, `table`, `report_qa`).
     - `SanitizedNeuroHeader`: PHI-stripped structural metadata (`shape`, `voxel_sizes_mm`, `orientation`, `tr_seconds`, `sampling_freq_hz`, `channel_count`, `dtype`, `nan_count`, `inf_count`, `value_range`, and `phi_sanitized: Literal[True] = True`).
     - `RemoteArtifact`: pointer model for remote neuro datasets (`artifact_id`, `uri` format `<host>:///<posix_path>`, `host`, `posix_path`, `modality`, `space`, `bids_entities`, `sha256_header`, `size_bytes`, `header_summary`).
     - `TaskState`: lifecycle state machine enum (`PENDING`, `PREFLIGHT_CHECK`, `RUNNING`, `QA_REVIEW`, `RETRYING`, `WAITING_OPERATOR`, `COMPLETED`, `FAILED`, `CANCELLED`).
     - `NeuriTaskEnvelope`: task payload dispatched to harness adapters (`workflow_id`, `node_id`, `agent_role`, `harness_id`, `execution_mode`, `system_prompt`, `task_instruction`, `skill_paths`, `mcp_servers`, `input_artifacts`, `max_tokens_budget`, `max_cost_usd`, `attempt_number`, `max_retries`, `diagnostic_feedback`).
     - `TelemetryEvent`: normalized telemetry event emitted by `TelemetryTap` (`event_id`, `workflow_id`, `node_id`, `harness_id`, `timestamp`, `event_type`, `thinking_text`, `input_tokens`, `cached_tokens`, `reasoning_tokens`, `output_tokens`, `estimated_cost_usd`, `tool_name`, `tool_host`, `tool_status`, `duration_ms`).
     - `NiiVueLayerSpec`: viewer volume or surface layer overlay (`artifact_uri`, `colormap`, `opacity`, `cal_min`, `cal_max`).
     - `NiiVueSceneSpec`: declarative 3D/multiplanar scene manifest (`scene_id`, `title`, `volumes`, `meshes`, `tractography_uris`, `crosshair_mni`, `slice_type`).

3. **PROJECT.md (Lines 18–31, 110–118):**
   - Interface contracts confirm that `SanitizedNeuroHeader` strictly enforces `phi_sanitized: Literal[True] = True`.
   - `TaskNode` and `TaskEdge` define Blackboard DAG topological units.
   - `NeuriTaskResult` defines harness output contract (`node_id`, `success`, `exit_code`, `summary`, `output_artifacts`, `tokens_consumed`, `cost_usd`).
   - `ChatRole`, `ChatTurn`, and `SessionEvent` structure session conversation turns and frontend streaming events.

4. **python_standard.md (Lines 9–38):**
   - Strict PEP 8 styling, 4-space indentation, 79–88 character line limit.
   - Explicit type hints on all arguments and return values.
   - Mandatory docstrings with `Parameters\n------------` and `Returns\n--------` blocks on all classes, methods, and functions.
   - Zero module-level global variables. Single return type and single return variable.

5. **Runtime Python Environment:**
   - Target Python is `>=3.12`. Python 3.12 deprecates `datetime.utcnow()` with `DeprecationWarning`; `datetime.now(timezone.utc)` is required for timezone-aware UTC timestamps.

---

## 2. Logic Chain

1. **Universal Contract Layer:**
   - *Observation:* Section 4.1 of the architecture spec and R1 of `ORIGINAL_REQUEST.md` establish that all subsystems—Blackboard (`blackboard.py`), Preflight (`preflight.py`), Harness Adapters (`adapters/`), Telemetry (`telemetry.py`), Orchestrator (`orchestrator.py`), Session Engine (`session.py`), and UI (`terminal_chat.py`)—depend directly on `src/neuri/core/schemas.py`.
   - *Reasoning:* A single schema failure, typing ambiguity, or loose validation cascades into every downstream component. Therefore, schemas must be strictly typed, forbid undeclared extra attributes (`extra="forbid"`), and perform explicit validation at instantiation time.

2. **Zero-Token PHI Sanitization Invariant:**
   - *Observation:* Requirement R1 and R5 explicitly require `SanitizedNeuroHeader` to enforce `phi_sanitized: Literal[True] = True`.
   - *Reasoning:* If a pipeline step attempts to construct a `SanitizedNeuroHeader` with `phi_sanitized=False`, Pydantic v2 type checking must immediately raise `pydantic.ValidationError` before the metadata can ever be passed to an LLM context or written to persistent logs. Using `Literal[True]` guarantees that non-sanitized data cannot be represented as a valid instance.

3. **POSIX URI and Topological Invariants:**
   - *Observation:* `RemoteArtifact.uri` requires format `<host_alias>:///<posix_path>`. `TaskEdge` connects `parent_node_id` to `child_node_id`.
   - *Reasoning:* Regex validation on `RemoteArtifact.uri` ensures cross-host path pointers are well-formed before persisting to SQLite or dispatching to Slurm/tmux. A validator on `TaskEdge` rejecting `parent_node_id == child_node_id` prevents trivial self-loop cycles in DAG construction.

4. **Python Standards (R8) & AST Enforcement:**
   - *Observation:* `python_standard.md` mandates that all functions, methods, and classes must have custom docstrings with `Parameters` and `Returns` blocks, zero globals, and 79–88 char line limits.
   - *Reasoning:* To ensure automated compliance checks (`tests/unit/test_standards_compliance.py`) pass without warnings, every class definition and every validation helper method in `schemas.py` must contain full `Parameters` and `Returns` blocks, type annotations, and maintain strict line wrapping under 88 characters.

---

## 3. Caveats

- **Timezone Standardization:** All timestamps use `datetime.now(timezone.utc)` instead of the deprecated `datetime.utcnow()`. Downstream consumers (e.g. SQLite serializers in `blackboard.py`) must serialize using `.isoformat()` to maintain uniform ISO-8601 strings.
- **Pydantic Model Mutability:** Models are defined with default mutability (`frozen=False`) to allow state updates by the Blackboard and Session Engine (e.g., updating `TaskNode.state` or `TaskNode.diagnostic_feedback`).
- **Extra Fields Guardrail:** `ConfigDict(extra="forbid")` is enabled on all models. This prevents accidental field misspelling or silent schema drift across harness versions.

---

## 4. Conclusion & Complete Implementation Specification

The complete, production-ready specification for `src/neuri/core/schemas.py` encompasses all 13 core models plus 2 supporting enumerations (`ChatRole` and `SessionEventType`), totaling 15 strongly-typed schema structures with zero global variables, full docstrings, and strict validation.

### 4.1 Target File: `src/neuri/core/schemas.py`

```python
"""Neuri Core Schemas module.

Defines canonical Pydantic v2 data models and enumerations for the Neuri
neuroscience meta-harness, including PHI-sanitized neuroimaging metadata,
remote artifacts, blackboard DAG nodes, task envelopes, telemetry events,
NiiVue scene specs, chat turns, and session engine streaming events.
"""

from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any, Literal
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class ModalityType(str, Enum):
    """Enumeration of supported neuroscience data modalities.

    Defines the canonical modality tags recognized across Neuri pipelines,
    including structural MRI, functional MRI, diffusion MRI, electrophysiology,
    Bayesian posteriors, tabular data, and QA reports.

    Parameters
    ------------
    None

    Returns
    --------
        ModalityType: ModalityType enum member
            Enumeration value representing the neuroscience modality.
    """

    T1W = "T1w"
    T2W = "T2w"
    BOLD = "bold"
    DWI = "dwi"
    TRACTOGRAPHY = "tractography"
    SURFACE = "surface"
    EEG = "eeg"
    MEG = "meg"
    IEEG = "ieeg"
    POSTERIOR = "posterior"
    TABLE = "table"
    REPORT_QA = "report_qa"


class SanitizedNeuroHeader(BaseModel):
    """PHI-stripped structural metadata safe for LLM context.

    Enforces that phi_sanitized is strictly True (<150 tokens) to guarantee
    zero protected health information leakage into external prompts or logs.

    Parameters
    ------------
    shape: list[int]
        Array dimensions of the volume or time series.
    voxel_sizes_mm: list[float] | None
        Voxel dimensions in millimeters. Defaults to None.
    orientation: str | None
        3-letter affine orientation code such as RAS or LPS. Defaults to None.
    tr_seconds: float | None
        Repetition time in seconds for fMRI acquisitions. Defaults to None.
    sampling_freq_hz: float | None
        Electrophysiology sampling frequency in Hertz. Defaults to None.
    channel_count: int | None
        Total number of recording channels. Defaults to None.
    dtype: str
        Numeric representation type string (e.g. float32, int16).
    nan_count: int
        Total count of NaN values present in data. Defaults to 0.
    inf_count: int
        Total count of infinite values present in data. Defaults to 0.
    value_range: tuple[float, float] | None
        Pair of (min_val, max_val) intensity values. Defaults to None.
    phi_sanitized: Literal[True]
        Strict literal flag asserting zero PHI. Defaults to True.

    Returns
    --------
        SanitizedNeuroHeader: SanitizedNeuroHeader instance
            Constructed structural metadata model.
    """

    model_config = ConfigDict(extra="forbid")

    shape: list[int] = Field(
        ...,
        description="Array dimensions, e.g. [256, 256, 176, 200]",
    )
    voxel_sizes_mm: list[float] | None = Field(
        default=None,
        description="Voxel zoom in millimeters",
    )
    orientation: str | None = Field(
        default=None,
        description="3-letter orientation code, e.g. RAS or LPS",
    )
    tr_seconds: float | None = Field(
        default=None,
        description="Repetition time in seconds (fMRI)",
    )
    sampling_freq_hz: float | None = Field(
        default=None,
        description="Sampling rate in Hz (EEG/MEG)",
    )
    channel_count: int | None = Field(
        default=None,
        description="Number of electrophysiology channels",
    )
    dtype: str = Field(
        ...,
        description="Numeric data type, e.g. float32, int16",
    )
    nan_count: int = Field(
        default=0,
        ge=0,
        description="Count of NaN values",
    )
    inf_count: int = Field(
        default=0,
        ge=0,
        description="Count of infinite values",
    )
    value_range: tuple[float, float] | None = Field(
        default=None,
        description="Tuple of (min_val, max_val)",
    )
    phi_sanitized: Literal[True] = Field(
        default=True,
        description="Strict literal flag asserting zero PHI",
    )

    @field_validator("orientation")
    @classmethod
    def validate_orientation(cls, value: str | None) -> str | None:
        """Validate 3-letter orientation string format.

        Parameters
        ------------
        value: str | None
            Candidate orientation string code.

        Returns
        --------
            str | None: validated orientation string or None.
        """
        if value is not None:
            clean_val = value.strip().upper()
            if len(clean_val) != 3:
                raise ValueError(
                    f"Orientation must be a 3-letter code, got '{value}'"
                )
            return clean_val
        return None

    @field_validator("shape")
    @classmethod
    def validate_shape(cls, value: list[int]) -> list[int]:
        """Validate that array dimensions are non-empty and strictly positive.

        Parameters
        ------------
        value: list[int]
            List of array dimension sizes.

        Returns
        --------
            list[int]: validated list of array dimensions.
        """
        if not value:
            raise ValueError("Array shape cannot be empty")
        for dim in value:
            if dim <= 0:
                raise ValueError(
                    f"Array dimensions must be positive, got {dim}"
                )
        return value

    @model_validator(mode="after")
    def validate_value_range(self) -> "SanitizedNeuroHeader":
        """Validate that minimum value does not exceed maximum value.

        Parameters
        ------------
        None

        Returns
        --------
            SanitizedNeuroHeader: validated instance.
        """
        if self.value_range is not None:
            min_val, max_val = self.value_range
            if min_val > max_val:
                raise ValueError(
                    f"Minimum value ({min_val}) cannot exceed maximum ({max_val})"
                )
        return self


class RemoteArtifact(BaseModel):
    """Pointer contract for remote neuroimaging datasets and outputs.

    Provides a vendor-agnostic pointer referencing files across local
    filesystems, compute nodes, or HPC clusters using standard POSIX URIs.

    Parameters
    ------------
    artifact_id: str
        Unique artifact identifier.
    uri: str
        Full URI adhering to format: host_alias:///abs/posix/path/to/file.
    host: str
        Target host identifier or alias (e.g. localhost, slurm_node).
    posix_path: str
        Absolute POSIX file path on the target host.
    modality: ModalityType
        Neuroscience data modality classification.
    space: str | None
        Standard coordinate space (e.g. MNI152NLin2009cAsym). Defaults to None.
    bids_entities: dict[str, str]
        Key-value dictionary of BIDS entity attributes. Defaults to empty dict.
    sha256_header: str
        SHA-256 hexadecimal hash digest of header bytes.
    size_bytes: int
        Total file size in bytes.
    header_summary: SanitizedNeuroHeader
        PHI-sanitized metadata summary.
    created_by_node: str | None
        DAG node ID that produced this artifact. Defaults to None.
    created_at: datetime
        UTC timestamp of artifact registration. Defaults to current UTC time.

    Returns
    --------
        RemoteArtifact: RemoteArtifact instance
            Constructed remote artifact pointer model.
    """

    model_config = ConfigDict(extra="forbid")

    artifact_id: str = Field(
        ...,
        description="Unique identifier for the remote artifact",
    )
    uri: str = Field(
        ...,
        description="Format: host_alias:///abs/posix/path/to/file",
    )
    host: str = Field(
        ...,
        description="Target host alias, e.g. localhost, cluster_node",
    )
    posix_path: str = Field(
        ...,
        description="Absolute POSIX path on the target host",
    )
    modality: ModalityType = Field(
        ...,
        description="Neuroscience modality type",
    )
    space: str | None = Field(
        default=None,
        description="Standard coordinate space, e.g. MNI152NLin2009cAsym",
    )
    bids_entities: dict[str, str] = Field(
        default_factory=dict,
        description="Key-value dictionary of BIDS entity attributes",
    )
    sha256_header: str = Field(
        ...,
        description="SHA-256 hash of the header metadata",
    )
    size_bytes: int = Field(
        ...,
        ge=0,
        description="Artifact file size in bytes",
    )
    header_summary: SanitizedNeuroHeader = Field(
        ...,
        description="Sanitized header summary with verified zero PHI",
    )
    created_by_node: str | None = Field(
        default=None,
        description="DAG node ID that produced this artifact",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp in UTC",
    )

    @field_validator("uri")
    @classmethod
    def validate_uri_format(cls, value: str) -> str:
        """Validate that URI adheres to the host_alias:///posix/path format.

        Parameters
        ------------
        value: str
            Raw URI string to validate.

        Returns
        --------
            str: validated URI string.
        """
        pattern = r"^[a-zA-Z0-9_\-]+:///.+$"
        if not re.match(pattern, value):
            raise ValueError(
                f"Invalid artifact URI '{value}'. Must follow format: "
                "<host_alias>:///abs/posix/path"
            )
        return value


class TaskState(str, Enum):
    """Lifecycle state machine for DAG task nodes.

    Defines valid execution states for DAG nodes tracked in the SQLite
    Blackboard, managing transitions from scheduling through QA review.

    Parameters
    ------------
    None

    Returns
    --------
        TaskState: TaskState enum member
            Enumeration value representing the task node state.
    """

    PENDING = "PENDING"
    PREFLIGHT_CHECK = "PREFLIGHT_CHECK"
    RUNNING = "RUNNING"
    QA_REVIEW = "QA_REVIEW"
    RETRYING = "RETRYING"
    WAITING_OPERATOR = "WAITING_OPERATOR"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    def is_terminal(self) -> bool:
        """Check if current state is an irreversible terminal state.

        Parameters
        ------------
        None

        Returns
        --------
            bool: True if state is COMPLETED, FAILED, or CANCELLED.
        """
        terminal_states = (
            TaskState.COMPLETED,
            TaskState.FAILED,
            TaskState.CANCELLED,
        )
        return self in terminal_states

    def is_active(self) -> bool:
        """Check if current state is currently executing or active.

        Parameters
        ------------
        None

        Returns
        --------
            bool: True if state is active.
        """
        active_states = (
            TaskState.PREFLIGHT_CHECK,
            TaskState.RUNNING,
            TaskState.QA_REVIEW,
            TaskState.RETRYING,
        )
        return self in active_states


class NeuriTaskEnvelope(BaseModel):
    """Normalized task payload dispatched to any BaseHarnessAdapter.

    Encapsulates all prompts, skill paths, MCP configurations, artifact
    pointers, and resource budgets needed for headless or interactive harness
    execution.

    Parameters
    ------------
    workflow_id: str
        Parent workflow identifier.
    node_id: str
        Unique DAG task node identifier.
    agent_role: str
        Neuroscience specialist role (e.g. neuroimaging_specialist).
    harness_id: str
        Target harness backend identifier (e.g. agy, codex, ollama).
    execution_mode: Literal["headless_json", "interactive_pty"]
        Execution mode. Defaults to "headless_json".
    system_prompt: str
        Persona constraints and system instructions.
    task_instruction: str
        Actionable prompt instructions for the step.
    skill_paths: list[str]
        Filesystem paths to relevant skill packs. Defaults to empty list.
    mcp_servers: dict[str, dict[str, Any]]
        Configuration dictionaries for MCP server tools. Defaults to empty.
    input_artifacts: list[RemoteArtifact]
        Remote artifacts available as inputs. Defaults to empty list.
    max_tokens_budget: int
        Token ceiling for node execution. Defaults to 64000.
    max_cost_usd: float
        Cost ceiling in USD. Defaults to 2.00.
    attempt_number: int
        Current execution attempt number (1-indexed). Defaults to 1.
    max_retries: int
        Maximum auto-retry attempts permitted. Defaults to 2.
    diagnostic_feedback: str | None
        Diagnostic feedback from previous failed attempt. Defaults to None.

    Returns
    --------
        NeuriTaskEnvelope: NeuriTaskEnvelope instance
            Constructed task envelope model.
    """

    model_config = ConfigDict(extra="forbid")

    workflow_id: str = Field(
        ...,
        description="Parent workflow identifier",
    )
    node_id: str = Field(
        ...,
        description="Unique task node identifier",
    )
    agent_role: str = Field(
        ...,
        description="Specialist agent role name",
    )
    harness_id: str = Field(
        ...,
        description="Target harness backend: agy, codex, opencode, openclaw, ollama",
    )
    execution_mode: Literal["headless_json", "interactive_pty"] = Field(
        default="headless_json",
        description="Execution mode: headless structured JSON or interactive PTY",
    )
    system_prompt: str = Field(
        ...,
        description="Persona constraints and system prompt",
    )
    task_instruction: str = Field(
        ...,
        description="Step instruction prompt",
    )
    skill_paths: list[str] = Field(
        default_factory=list,
        description="Filesystem paths to relevant skill packs",
    )
    mcp_servers: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="MCP server configuration dictionaries",
    )
    input_artifacts: list[RemoteArtifact] = Field(
        default_factory=list,
        description="Input remote artifacts required for task execution",
    )
    max_tokens_budget: int = Field(
        default=64000,
        gt=0,
        description="Token consumption ceiling for node execution",
    )
    max_cost_usd: float = Field(
        default=2.00,
        gt=0.0,
        description="Cost budget ceiling in USD",
    )
    attempt_number: int = Field(
        default=1,
        ge=1,
        description="Current execution attempt number (1-indexed)",
    )
    max_retries: int = Field(
        default=2,
        ge=0,
        description="Maximum auto-retry attempts permitted",
    )
    diagnostic_feedback: str | None = Field(
        default=None,
        description="Diagnostic feedback from previous failed attempt",
    )


class NeuriTaskResult(BaseModel):
    """Structured execution result returned by a harness execution.

    Represents the final outcome of an executed task envelope, capturing
    exit status, generated artifacts, token consumption, and diagnostics.

    Parameters
    ------------
    node_id: str
        Target node identifier.
    success: bool
        Whether execution completed successfully.
    exit_code: int
        Process or harness status code (0 for success).
    summary: str
        Human-readable execution outcome summary.
    artifacts_emitted: list[RemoteArtifact]
        List of remote artifacts produced by the task. Defaults to empty list.
    total_tokens: int
        Total tokens consumed across prompt and completion. Defaults to 0.
    cost_usd: float
        Estimated USD cost for the run. Defaults to 0.0.
    error_message: str | None
        Error details if execution failed. Defaults to None.
    raw_output: str | None
        Raw transcript or output snippet. Defaults to None.

    Returns
    --------
        NeuriTaskResult: NeuriTaskResult instance
            Constructed execution result model.
    """

    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(
        ...,
        description="Target node identifier",
    )
    success: bool = Field(
        ...,
        description="Whether execution completed successfully",
    )
    exit_code: int = Field(
        ...,
        description="Process or harness status code",
    )
    summary: str = Field(
        ...,
        description="Human-readable execution outcome summary",
    )
    artifacts_emitted: list[RemoteArtifact] = Field(
        default_factory=list,
        description="List of remote artifacts produced by the task",
    )
    total_tokens: int = Field(
        default=0,
        ge=0,
        description="Total tokens consumed across execution",
    )
    cost_usd: float = Field(
        default=0.0,
        ge=0.0,
        description="Estimated USD cost for the run",
    )
    error_message: str | None = Field(
        default=None,
        description="Error details if execution failed",
    )
    raw_output: str | None = Field(
        default=None,
        description="Raw transcript or output snippet",
    )

    def is_ok(self) -> bool:
        """Check if execution succeeded cleanly with zero exit code.

        Parameters
        ------------
        None

        Returns
        --------
            bool: True if execution succeeded and exit code is 0.
        """
        is_clean = self.success and self.exit_code == 0
        return is_clean


class TaskNode(BaseModel):
    """Blackboard representation of a DAG task node.

    Tracks execution state, attempt counts, dispatched envelopes, and
    diagnostics across the SQLite Blackboard.

    Parameters
    ------------
    node_id: str
        Unique node identifier.
    workflow_id: str
        Parent workflow identifier.
    agent_role: str
        Specialist agent role assigned to this node.
    harness_id: str
        Execution harness identifier.
    state: TaskState
        Current execution state. Defaults to TaskState.PENDING.
    attempt: int
        Current retry attempt count. Defaults to 0.
    max_retries: int
        Maximum allowed auto-retry attempts. Defaults to 2.
    envelope: NeuriTaskEnvelope | None
        Dispatched task envelope. Defaults to None.
    summary_result: str | None
        Human-readable execution outcome summary. Defaults to None.
    diagnostic_feedback: str | None
        Diagnostic feedback for retry. Defaults to None.
    started_at: datetime | None
        Timestamp when node entered RUNNING state. Defaults to None.
    completed_at: datetime | None
        Timestamp when node reached terminal state. Defaults to None.

    Returns
    --------
        TaskNode: TaskNode instance
            Constructed task node model.
    """

    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(
        ...,
        description="Unique node identifier",
    )
    workflow_id: str = Field(
        ...,
        description="Parent workflow identifier",
    )
    agent_role: str = Field(
        ...,
        description="Specialist agent role assigned to this node",
    )
    harness_id: str = Field(
        ...,
        description="Execution harness identifier, e.g. agy, codex",
    )
    state: TaskState = Field(
        default=TaskState.PENDING,
        description="Current execution state",
    )
    attempt: int = Field(
        default=0,
        ge=0,
        description="Current retry attempt count",
    )
    max_retries: int = Field(
        default=2,
        ge=0,
        description="Maximum allowed auto-retry attempts",
    )
    envelope: NeuriTaskEnvelope | None = Field(
        default=None,
        description="Dispatched task envelope",
    )
    summary_result: str | None = Field(
        default=None,
        description="Human-readable execution outcome summary",
    )
    diagnostic_feedback: str | None = Field(
        default=None,
        description="Diagnostic error feedback for retry",
    )
    started_at: datetime | None = Field(
        default=None,
        description="Timestamp when node entered RUNNING state",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="Timestamp when node reached terminal state",
    )


class TaskEdge(BaseModel):
    """Directed edge representing dependency between two task nodes.

    Defines that parent_node_id must reach COMPLETED state before
    child_node_id becomes eligible for scheduling.

    Parameters
    ------------
    workflow_id: str
        Parent workflow identifier.
    parent_node_id: str
        Identifier of the predecessor node.
    child_node_id: str
        Identifier of the successor node.

    Returns
    --------
        TaskEdge: TaskEdge instance
            Constructed task edge model.
    """

    model_config = ConfigDict(extra="forbid")

    workflow_id: str = Field(
        ...,
        description="Parent workflow identifier",
    )
    parent_node_id: str = Field(
        ...,
        description="Dependency predecessor node identifier",
    )
    child_node_id: str = Field(
        ...,
        description="Dependent successor node identifier",
    )

    @model_validator(mode="after")
    def validate_no_self_loop(self) -> "TaskEdge":
        """Validate that an edge does not connect a node to itself.

        Parameters
        ------------
        None

        Returns
        --------
            TaskEdge: validated task edge instance.
        """
        if self.parent_node_id == self.child_node_id:
            raise ValueError(
                f"Self-loop detected: parent and child node ID is {self.parent_node_id}"
            )
        return self


class TelemetryEvent(BaseModel):
    """Unified telemetry event emitted by TelemetryTap across all harnesses.

    Captures granular stream deltas, thinking blocks, token counts, and
    circuit breaker trips from diverse harness streams.

    Parameters
    ------------
    event_id: str
        Unique event identifier.
    workflow_id: str
        Workflow identifier.
    node_id: str
        Node identifier.
    harness_id: str
        Harness identifier.
    timestamp: datetime
        UTC timestamp of event creation. Defaults to current UTC time.
    event_type: Literal["thinking_delta", "token_usage", "tool_lifecycle", "circuit_breaker"]
        Normalized event category.
    thinking_text: str | None
        Extracted reasoning text delta. Defaults to None.
    input_tokens: int
        Cumulative input tokens. Defaults to 0.
    cached_tokens: int
        Prompt cached tokens. Defaults to 0.
    reasoning_tokens: int
        Thinking tokens consumed. Defaults to 0.
    output_tokens: int
        Completion output tokens. Defaults to 0.
    estimated_cost_usd: float
        Accumulated cost in USD. Defaults to 0.0.
    tool_name: str | None
        Name of tool invoked. Defaults to None.
    tool_host: str | None
        Host where tool was executed. Defaults to None.
    tool_status: Literal["started", "completed", "failed"] | None
        Tool execution status. Defaults to None.
    duration_ms: int | None
        Execution duration in milliseconds. Defaults to None.
    breaker_reason: str | None
        Reason circuit breaker tripped. Defaults to None.

    Returns
    --------
        TelemetryEvent: TelemetryEvent instance
            Constructed telemetry event model.
    """

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(
        ...,
        description="Unique event identifier",
    )
    workflow_id: str = Field(
        ...,
        description="Workflow identifier",
    )
    node_id: str = Field(
        ...,
        description="Node identifier",
    )
    harness_id: str = Field(
        ...,
        description="Harness identifier",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp in UTC",
    )
    event_type: Literal[
        "thinking_delta",
        "token_usage",
        "tool_lifecycle",
        "circuit_breaker",
    ] = Field(
        ...,
        description="Normalized event category",
    )
    thinking_text: str | None = Field(
        default=None,
        description="Extracted reasoning text delta",
    )
    input_tokens: int = Field(
        default=0,
        ge=0,
        description="Cumulative or incremental input tokens",
    )
    cached_tokens: int = Field(
        default=0,
        ge=0,
        description="Prompt cached tokens",
    )
    reasoning_tokens: int = Field(
        default=0,
        ge=0,
        description="Thinking tokens consumed",
    )
    output_tokens: int = Field(
        default=0,
        ge=0,
        description="Completion output tokens",
    )
    estimated_cost_usd: float = Field(
        default=0.0,
        ge=0.0,
        description="Accumulated cost in USD",
    )
    tool_name: str | None = Field(
        default=None,
        description="Name of tool invoked",
    )
    tool_host: str | None = Field(
        default=None,
        description="Host where tool was executed",
    )
    tool_status: Literal["started", "completed", "failed"] | None = Field(
        default=None,
        description="Tool execution status",
    )
    duration_ms: int | None = Field(
        default=None,
        ge=0,
        description="Execution duration in milliseconds",
    )
    breaker_reason: str | None = Field(
        default=None,
        description="Reason circuit breaker tripped",
    )


class NiiVueLayerSpec(BaseModel):
    """Specification of a visual volume or mesh layer in NiiVue.

    Configures colormap, opacity, and intensity calibration ranges for
    neuroimaging overlays in 3D/multiplanar viewers.

    Parameters
    ------------
    artifact_uri: str
        Remote artifact URI pointing to the volume or surface file.
    colormap: str
        Color map name (e.g. gray, warm, cold, jet). Defaults to "gray".
    opacity: float
        Layer opacity between 0.0 and 1.0. Defaults to 1.0.
    cal_min: float | None
        Minimum intensity calibration display threshold. Defaults to None.
    cal_max: float | None
        Maximum intensity calibration display threshold. Defaults to None.

    Returns
    --------
        NiiVueLayerSpec: NiiVueLayerSpec instance
            Constructed layer specification model.
    """

    model_config = ConfigDict(extra="forbid")

    artifact_uri: str = Field(
        ...,
        description="Remote artifact URI for the volume or surface",
    )
    colormap: str = Field(
        default="gray",
        description="Color map name, e.g. gray, warm, cold, jet",
    )
    opacity: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Layer opacity between 0.0 and 1.0",
    )
    cal_min: float | None = Field(
        default=None,
        description="Minimum calibration display threshold",
    )
    cal_max: float | None = Field(
        default=None,
        description="Maximum calibration display threshold",
    )

    @model_validator(mode="after")
    def validate_calibration_range(self) -> "NiiVueLayerSpec":
        """Validate calibration min is less than or equal to calibration max.

        Parameters
        ------------
        None

        Returns
        --------
            NiiVueLayerSpec: validated layer specification instance.
        """
        if self.cal_min is not None and self.cal_max is not None:
            if self.cal_min > self.cal_max:
                raise ValueError(
                    f"cal_min ({self.cal_min}) cannot exceed "
                    f"cal_max ({self.cal_max})"
                )
        return self


class NiiVueSceneSpec(BaseModel):
    """Declarative scene manifest pushed over WebSocket to the local NiiVue viewer.

    Provides a complete declarative recipe for multiplanar volume slicing,
    surface meshes, tractography streamlines, and crosshair coordinates.

    Parameters
    ------------
    scene_id: str
        Unique scene identifier.
    title: str
        Human-readable scene title.
    volumes: list[NiiVueLayerSpec]
        Ordered list of volume layers to load.
    meshes: list[NiiVueLayerSpec]
        Surface mesh layers to display. Defaults to empty list.
    tractography_uris: list[str]
        List of streamline tractography URIs. Defaults to empty list.
    crosshair_mni: tuple[float, float, float]
        Initial crosshair coordinates in MNI space (x, y, z). Defaults to (0, 0, 0).
    slice_type: Literal["multiplanar", "axial", "coronal", "sagittal", "render3d"]
        Viewer display layout mode. Defaults to "multiplanar".

    Returns
    --------
        NiiVueSceneSpec: NiiVueSceneSpec instance
            Constructed scene specification model.
    """

    model_config = ConfigDict(extra="forbid")

    scene_id: str = Field(
        ...,
        description="Unique scene identifier",
    )
    title: str = Field(
        ...,
        description="Human-readable scene title",
    )
    volumes: list[NiiVueLayerSpec] = Field(
        ...,
        description="Ordered list of volume layers",
    )
    meshes: list[NiiVueLayerSpec] = Field(
        default_factory=list,
        description="Surface mesh layers",
    )
    tractography_uris: list[str] = Field(
        default_factory=list,
        description="Tractography streamline URIs",
    )
    crosshair_mni: tuple[float, float, float] = Field(
        default=(0.0, 0.0, 0.0),
        description="Initial crosshair MNI coordinates (x, y, z)",
    )
    slice_type: Literal[
        "multiplanar",
        "axial",
        "coronal",
        "sagittal",
        "render3d",
    ] = Field(
        default="multiplanar",
        description="Viewer display layout mode",
    )


class ChatRole(str, Enum):
    """Role in a chat interaction turn.

    Differentiates participant personas in interactive sessions.

    Parameters
    ------------
    None

    Returns
    --------
        ChatRole: ChatRole enum member
            Enumeration value representing the conversation participant role.
    """

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    OPERATOR = "operator"


class ChatTurn(BaseModel):
    """Single turn in an interactive chat session.

    Preserves conversational history, thinking traces, and associations to
    Blackboard workflow and node identifiers.

    Parameters
    ------------
    turn_id: str
        Unique turn identifier.
    role: ChatRole
        Conversation participant role.
    content: str
        Textual message content.
    timestamp: datetime
        UTC timestamp of message creation. Defaults to current UTC time.
    node_id: str | None
        Associated DAG node ID if applicable. Defaults to None.
    workflow_id: str | None
        Associated workflow ID if applicable. Defaults to None.
    thinking_trace: str | None
        Reasoning trace text. Defaults to None.

    Returns
    --------
        ChatTurn: ChatTurn instance
            Constructed chat turn model.
    """

    model_config = ConfigDict(extra="forbid")

    turn_id: str = Field(
        ...,
        description="Unique turn identifier",
    )
    role: ChatRole = Field(
        ...,
        description="Conversation participant role",
    )
    content: str = Field(
        ...,
        description="Textual turn content",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the turn",
    )
    node_id: str | None = Field(
        default=None,
        description="Associated DAG node ID if applicable",
    )
    workflow_id: str | None = Field(
        default=None,
        description="Associated workflow ID if applicable",
    )
    thinking_trace: str | None = Field(
        default=None,
        description="Extracted reasoning thinking trace",
    )


class SessionEventType(str, Enum):
    """Type of session event emitted by NeuriSessionEngine.

    Categorizes streaming events dispatched to frontends (Textual UI or CLI).

    Parameters
    ------------
    None

    Returns
    --------
        SessionEventType: SessionEventType enum member
            Enumeration value representing the session event type.
    """

    USER_MESSAGE = "user_message"
    ASSISTANT_CHUNK = "assistant_chunk"
    THINKING_CHUNK = "thinking_chunk"
    STATUS_UPDATE = "status_update"
    DAG_NODE_UPDATE = "dag_node_update"
    TOOL_CALL_UPDATE = "tool_call_update"
    CIRCUIT_BREAKER_TRIGGERED = "circuit_breaker_triggered"
    ERROR = "error"
    WORKFLOW_COMPLETED = "workflow_completed"


class SessionEvent(BaseModel):
    """Typed streaming event emitted by the UI-agnostic Session Engine.

    Carries payload data to decoupling presentation frontends from core
    orchestration and telemetry streams.

    Parameters
    ------------
    event_id: str
        Unique session event identifier.
    session_id: str
        Interactive session identifier.
    event_type: SessionEventType
        Category of session event.
    timestamp: datetime
        UTC timestamp of event generation. Defaults to current UTC time.
    payload: dict[str, Any]
        Arbitrary typed event payload dictionary. Defaults to empty dict.

    Returns
    --------
        SessionEvent: SessionEvent instance
            Constructed session event model.
    """

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(
        ...,
        description="Unique session event identifier",
    )
    session_id: str = Field(
        ...,
        description="Interactive session identifier",
    )
    event_type: SessionEventType = Field(
        ...,
        description="Category of the session event",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp in UTC",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary typed event payload dictionary",
    )
```

---

## 5. Verification Method

To independently verify the schemas once implemented in `src/neuri/core/schemas.py`:

### 5.1 Automated Test Execution Command
```bash
uv run pytest tests/unit/test_schemas.py -v
```

### 5.2 Test Suite Specification (`tests/unit/test_schemas.py`)

The test suite must verify the following 22 concrete test scenarios:

1. **`test_modality_type_members`**:
   - Asserts all 12 modalities are valid (`ModalityType.T1W.value == "T1w"`, `ModalityType.BOLD.value == "bold"`).
   - Asserts invalid string raises `ValueError` when cast to `ModalityType`.

2. **`test_sanitized_neuro_header_valid`**:
   - Constructs valid header with `shape=[256, 256, 176]`, `dtype="float32"`, `orientation="RAS"`, `voxel_sizes_mm=[1.0, 1.0, 1.0]`.
   - Asserts `header.phi_sanitized is True`.

3. **`test_sanitized_neuro_header_phi_rejection`**:
   - Passes `phi_sanitized=False` to `SanitizedNeuroHeader(...)`.
   - Asserts `pydantic.ValidationError` is raised with error locating `phi_sanitized`.

4. **`test_sanitized_neuro_header_invalid_shape`**:
   - Passes empty list `shape=[]` or negative dimension `shape=[256, -1, 176]`.
   - Asserts `ValidationError` is raised.

5. **`test_sanitized_neuro_header_invalid_orientation`**:
   - Passes 2-letter or 4-letter orientation (e.g. `"RA"` or `"RASP"`).
   - Asserts `ValidationError` is raised.

6. **`test_sanitized_neuro_header_invalid_value_range`**:
   - Passes `value_range=(100.0, 50.0)`.
   - Asserts `ValidationError` is raised (`min > max`).

7. **`test_remote_artifact_valid`**:
   - Constructs `RemoteArtifact` with valid URI `"localhost:///data/bids/sub-01/anat/sub-01_T1w.nii.gz"`.
   - Asserts attributes match and serialization produces valid JSON.

8. **`test_remote_artifact_invalid_uri`**:
   - Passes relative path `"relative/file.nii.gz"` or missing triple-slash `"localhost://path"`.
   - Asserts `ValidationError` is raised.

9. **`test_remote_artifact_negative_size`**:
   - Passes `size_bytes=-5`.
   - Asserts `ValidationError` is raised (`ge=0`).

10. **`test_task_state_lifecycle`**:
    - Tests `TaskState.COMPLETED.is_terminal()` returns `True`.
    - Tests `TaskState.RUNNING.is_terminal()` returns `False`.
    - Tests `TaskState.RUNNING.is_active()` returns `True`.
    - Tests `TaskState.COMPLETED.is_active()` returns `False`.

11. **`test_task_node_defaults`**:
    - Constructs `TaskNode` with required fields.
    - Asserts `state == TaskState.PENDING`, `attempt == 0`, `max_retries == 2`.

12. **`test_task_edge_valid`**:
    - Constructs `TaskEdge(workflow_id="wf_1", parent_node_id="n1", child_node_id="n2")`.
    - Asserts edge is created successfully.

13. **`test_task_edge_self_loop_rejection`**:
    - Constructs `TaskEdge(workflow_id="wf_1", parent_node_id="n1", child_node_id="n1")`.
    - Asserts `ValidationError` is raised for self-loop.

14. **`test_neuri_task_envelope_valid`**:
    - Constructs `NeuriTaskEnvelope` with valid budgets (`max_tokens_budget=64000`, `max_cost_usd=2.00`).
    - Asserts defaults and field accessibility.

15. **`test_neuri_task_envelope_invalid_budgets`**:
    - Passes `max_tokens_budget=0` or `max_cost_usd=-1.0`.
    - Asserts `ValidationError` is raised.

16. **`test_neuri_task_result_is_ok`**:
    - Success with `exit_code=0` yields `result.is_ok() is True`.
    - Success with `exit_code=1` yields `result.is_ok() is False`.
    - `success=False` with `exit_code=0` yields `result.is_ok() is False`.

17. **`test_telemetry_event_valid`**:
    - Validates `TelemetryEvent` with `event_type="thinking_delta"` and `thinking_text="reasoning..."`.
    - Asserts UTC timestamp is populated automatically.

18. **`test_niivue_layer_spec_opacity_range`**:
    - Passes `opacity=1.5` or `opacity=-0.1`.
    - Asserts `ValidationError` is raised.

19. **`test_niivue_layer_spec_cal_min_max`**:
    - Passes `cal_min=10.0` and `cal_max=5.0`.
    - Asserts `ValidationError` is raised.

20. **`test_niivue_scene_spec_valid`**:
    - Constructs `NiiVueSceneSpec` with volume layers and crosshair tuple.
    - Asserts `slice_type="multiplanar"` default.

21. **`test_chat_role_and_turn`**:
    - Constructs `ChatTurn` with `role=ChatRole.USER`.
    - Asserts JSON serialization roundtrip works cleanly.

22. **`test_session_event_valid`**:
    - Constructs `SessionEvent` with `event_type=SessionEventType.STATUS_UPDATE`.
    - Asserts payload dictionary preserves arbitrary typed keys.

### 5.3 Standards AST Verification Command
```bash
uv run pytest tests/unit/test_standards_compliance.py -v
```
- Asserts 100% adherence to `python_standard.md` (no globals, full type annotations, custom docstring format with `Parameters` and `Returns` blocks, lines $\le 88$ chars).
