"""Neuri Core Schemas module.

Defines canonical Pydantic v2 data models and enumerations for the Neuri
neuroscience meta-harness, including PHI-sanitized neuroimaging metadata,
remote artifacts, blackboard DAG nodes, task envelopes, telemetry events,
NiiVue scene specs, chat turns, and session engine streaming events.
"""

from datetime import datetime, timezone
from enum import Enum
import math
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
    including structural MRI, functional MRI, diffusion MRI,
    electrophysiology, Bayesian posteriors, tabular data, and QA reports.

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
    Instances are immutable (frozen) to prevent post-instantiation mutation.

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

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )

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
        gt=0.0,
        description="Repetition time in seconds (fMRI)",
    )
    sampling_freq_hz: float | None = Field(
        default=None,
        gt=0.0,
        description="Sampling rate in Hz (EEG/MEG)",
    )
    channel_count: int | None = Field(
        default=None,
        ge=1,
        description="Number of electrophysiology channels",
    )
    dtype: str = Field(
        ...,
        max_length=16,
        pattern=r"^[a-zA-Z0-9_\-]+$",
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
            str | None: string or None
                Validated 3-letter orientation string or None.
        """
        result_val: str | None = None
        if value is not None:
            clean_val: str = value.strip().upper()
            if len(clean_val) != 3:
                raise ValueError(
                    f"Orientation must be a 3-letter code, got '{value}'"
                )
            result_val = clean_val
        return result_val

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
            list[int]: list object
                Validated list of array dimensions.
        """
        if not value:
            raise ValueError("Array shape cannot be empty")
        for dim in value:
            if dim <= 0:
                raise ValueError(
                    f"Array dimensions must be positive, got {dim}"
                )
        validated_shape: list[int] = value
        return validated_shape

    @field_validator("voxel_sizes_mm")
    @classmethod
    def validate_voxel_sizes(
        cls, value: list[float] | None
    ) -> list[float] | None:
        """Validate that voxel dimensions are positive and finite numbers.

        Parameters
        ------------
        value: list[float] | None
            Candidate voxel sizes in millimeters.

        Returns
        --------
            list[float] | None: list of float or None
                Validated voxel zoom list.
        """
        if value is not None:
            if not value:
                raise ValueError("voxel_sizes_mm cannot be an empty list")
            for zoom in value:
                if not math.isfinite(zoom) or zoom <= 0.0:
                    raise ValueError(
                        f"Voxel dimensions must be finite and positive (>0), "
                        f"got {zoom}"
                    )
        validated_zooms: list[float] | None = value
        return validated_zooms

    @field_validator("tr_seconds")
    @classmethod
    def validate_tr_seconds(cls, value: float | None) -> float | None:
        """Validate that repetition time is a finite positive number.

        Parameters
        ------------
        value: float | None
            Candidate repetition time in seconds.

        Returns
        --------
            float | None: float or None
                Validated repetition time.
        """
        if value is not None:
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(
                    f"Repetition time (tr_seconds) must be finite and > 0, "
                    f"got {value}"
                )
        validated_tr: float | None = value
        return validated_tr

    @field_validator("sampling_freq_hz")
    @classmethod
    def validate_sampling_freq(cls, value: float | None) -> float | None:
        """Validate that electrophysiology sampling frequency is positive.

        Parameters
        ------------
        value: float | None
            Candidate sampling frequency in Hertz.

        Returns
        --------
            float | None: float or None
                Validated sampling frequency.
        """
        if value is not None:
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(
                    f"Sampling frequency (sampling_freq_hz) must be finite "
                    f"and > 0, got {value}"
                )
        validated_freq: float | None = value
        return validated_freq

    @model_validator(mode="after")
    def validate_value_range(self) -> "SanitizedNeuroHeader":
        """Validate that value_range is finite and min does not exceed max.

        Parameters
        ------------
        None

        Returns
        --------
            SanitizedNeuroHeader: SanitizedNeuroHeader instance
                Validated model instance.
        """
        if self.value_range is not None:
            min_val, max_val = self.value_range
            if not math.isfinite(min_val) or not math.isfinite(max_val):
                raise ValueError(
                    f"value_range components must be finite real numbers, "
                    f"got ({min_val}, {max_val})"
                )
            if min_val > max_val:
                raise ValueError(
                    f"Minimum value ({min_val}) cannot exceed "
                    f"maximum ({max_val})"
                )
        validated_self: SanitizedNeuroHeader = self
        return validated_self



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
        pattern=r"^[0-9a-f]{64}$",
        description=(
            "SHA-256 lowercase hexadecimal hash digest of header metadata"
        ),
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
            str: string object
                Validated URI string adhering to host:///path format.
        """
        pattern = r"^[a-zA-Z0-9_\-]+:///.+$"
        if not re.match(pattern, value):
            raise ValueError(
                f"Invalid artifact URI '{value}'. Must follow format: "
                "<host_alias>:///abs/posix/path"
            )
        result: str = value
        return result

    @field_validator("posix_path")
    @classmethod
    def validate_posix_path_absolute(cls, value: str) -> str:
        """Validate that posix_path is an absolute path starting with '/'.

        Parameters
        ------------
        value: str
            POSIX path string to validate.

        Returns
        --------
            str: string object
                Validated absolute POSIX path.
        """
        if not value.startswith("/"):
            raise ValueError(
                f"posix_path must be an absolute path starting with '/', "
                f"got '{value}'"
            )
        result: str = value
        return result

    @model_validator(mode="after")
    def validate_uri_matches_host_and_path(self) -> "RemoteArtifact":
        """Validate consistency between uri, host, and posix_path.

        Parameters
        ------------
        None

        Returns
        --------
            RemoteArtifact: RemoteArtifact instance
                Validated remote artifact model.
        """
        expected_uri: str = f"{self.host}://{self.posix_path}"
        if self.uri != expected_uri:
            raise ValueError(
                f"Artifact uri '{self.uri}' does not match expected format "
                f"'{expected_uri}' derived from host '{self.host}' and "
                f"posix_path '{self.posix_path}'."
            )
        result: RemoteArtifact = self
        return result


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
            bool: boolean object
                True if state is COMPLETED, FAILED, or CANCELLED.
        """
        terminal_states = (
            TaskState.COMPLETED,
            TaskState.FAILED,
            TaskState.CANCELLED,
        )
        is_term: bool = self in terminal_states
        return is_term

    def is_active(self) -> bool:
        """Check if current state is currently executing or active.

        Parameters
        ------------
        None

        Returns
        --------
            bool: boolean object
                True if state is active (PREFLIGHT_CHECK, RUNNING,
                QA_REVIEW, or RETRYING).
        """
        active_states = (
            TaskState.PREFLIGHT_CHECK,
            TaskState.RUNNING,
            TaskState.QA_REVIEW,
            TaskState.RETRYING,
        )
        is_act: bool = self in active_states
        return is_act


class NeuriTaskEnvelope(BaseModel):
    """Normalized task payload dispatched to any BaseHarnessAdapter.

    Encapsulates all prompts, skill paths, MCP configurations, artifact
    pointers, and resource budgets needed for headless or interactive
    harness execution.

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
        description=(
            "Target harness backend: agy, codex, opencode, openclaw, ollama"
        ),
    )
    execution_mode: Literal["headless_json", "interactive_pty"] = Field(
        default="headless_json",
        description="Execution mode: headless_json or interactive_pty",
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

    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, data: Any) -> Any:
        """Normalize property aliases like role and harness to canonical names.

        Parameters
        ------------
        data: Any
            Input data before model validation.

        Returns
        --------
            Any: Any object
                Normalized dictionary mapping alias keys to canonical names.
        """
        result: Any = data
        if isinstance(data, dict):
            normalized: dict[str, Any] = dict(data)
            if "role" in normalized:
                role_val: Any = normalized.pop("role")
                if "agent_role" not in normalized:
                    normalized["agent_role"] = role_val
                elif normalized["agent_role"] != role_val:
                    raise ValueError(
                        f"Conflicting values provided for 'role' "
                        f"({role_val!r}) and 'agent_role' "
                        f"({normalized['agent_role']!r})."
                    )
            if "harness" in normalized:
                harness_val: Any = normalized.pop("harness")
                if "harness_id" not in normalized:
                    normalized["harness_id"] = harness_val
                elif normalized["harness_id"] != harness_val:
                    raise ValueError(
                        f"Conflicting values provided for 'harness' "
                        f"({harness_val!r}) and 'harness_id' "
                        f"({normalized['harness_id']!r})."
                    )
            result = normalized
        return result

    @field_validator("diagnostic_feedback", mode="before")
    @classmethod
    def normalize_diagnostic_feedback(cls, value: Any) -> str | None:
        """Normalize diagnostic feedback to a consolidated string or None.

        Parameters
        ------------
        value: Any
            Input feedback string, list of strings, or None.

        Returns
        --------
            str | None: string or None
                Consolidated diagnostic feedback string.
        """
        result: str | None = None
        if value is None:
            return result
        if isinstance(value, (list, tuple)):
            entries: list[str] = [
                str(item).strip() for item in value if str(item).strip()
            ]
            if entries:
                result = "\n".join(entries)
            return result
        str_val: str = str(value).strip()
        if str_val:
            result = str_val
        return result

    @property
    def role(self) -> str:
        """Provide alias for agent_role matching PROJECT.md interface.

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                Specialist agent role name.
        """
        result: str = self.agent_role
        return result

    @property
    def harness(self) -> str:
        """Provide alias for harness_id matching PROJECT.md interface.

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                Target harness identifier.
        """
        result: str = self.harness_id
        return result



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

    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, data: Any) -> Any:
        """Normalize property aliases like output_artifacts and tokens_consumed.

        Parameters
        ------------
        data: Any
            Input data before model validation.

        Returns
        --------
            Any: Any object
                Normalized dictionary mapping alias keys to canonical names.
        """
        if isinstance(data, dict):
            normalized: dict[str, Any] = dict(data)
            if (
                "output_artifacts" in normalized
                and "artifacts_emitted" not in normalized
            ):
                normalized["artifacts_emitted"] = normalized.pop(
                    "output_artifacts"
                )
            if (
                "tokens_consumed" in normalized
                and "total_tokens" not in normalized
            ):
                normalized["total_tokens"] = normalized.pop("tokens_consumed")
            return normalized
        return data

    @property
    def output_artifacts(self) -> list[RemoteArtifact]:
        """Provide alias for artifacts_emitted matching PROJECT.md interface.

        Parameters
        ------------
        None

        Returns
        --------
            list[RemoteArtifact]: list object
                List of remote artifacts produced.
        """
        result: list[RemoteArtifact] = self.artifacts_emitted
        return result

    @property
    def tokens_consumed(self) -> int:
        """Provide alias for total_tokens matching PROJECT.md interface.

        Parameters
        ------------
        None

        Returns
        --------
            int: integer object
                Total token count consumed.
        """
        result: int = self.total_tokens
        return result

    def is_ok(self) -> bool:
        """Check if execution succeeded cleanly with zero exit code.

        Parameters
        ------------
        None

        Returns
        --------
            bool: boolean object
                True if execution succeeded and exit code is 0.
        """
        is_clean: bool = self.success and self.exit_code == 0
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
    diagnostic_feedback: list[str] | str | None
        Diagnostic feedback for retry. Defaults to empty list.
    created_at: str | None
        Creation timestamp in ISO 8601 UTC format. Defaults to None.
    updated_at: str | None
        Last update timestamp in ISO 8601 UTC format. Defaults to None.
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
    diagnostic_feedback: list[str] = Field(
        default_factory=list,
        description="Diagnostic error feedback entries for retry",
    )
    created_at: str | None = Field(
        default=None,
        description="Creation timestamp in ISO 8601 UTC format",
    )
    updated_at: str | None = Field(
        default=None,
        description="Last update timestamp in ISO 8601 UTC format",
    )
    started_at: datetime | None = Field(
        default=None,
        description="Timestamp when node entered RUNNING state",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="Timestamp when node reached terminal state",
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, data: Any) -> Any:
        """Normalize property aliases like role and harness to canonical names.

        Parameters
        ------------
        data: Any
            Input data before model validation.

        Returns
        --------
            Any: Any object
                Normalized dictionary mapping alias keys to canonical names.
        """
        result: Any = data
        if isinstance(data, dict):
            normalized: dict[str, Any] = dict(data)
            if "role" in normalized:
                role_val: Any = normalized.pop("role")
                if "agent_role" not in normalized:
                    normalized["agent_role"] = role_val
                elif normalized["agent_role"] != role_val:
                    raise ValueError(
                        f"Conflicting values provided for 'role' "
                        f"({role_val!r}) and 'agent_role' "
                        f"({normalized['agent_role']!r})."
                    )
            if "harness" in normalized:
                harness_val: Any = normalized.pop("harness")
                if "harness_id" not in normalized:
                    normalized["harness_id"] = harness_val
                elif normalized["harness_id"] != harness_val:
                    raise ValueError(
                        f"Conflicting values provided for 'harness' "
                        f"({harness_val!r}) and 'harness_id' "
                        f"({normalized['harness_id']!r})."
                    )
            result = normalized
        return result

    @field_validator("diagnostic_feedback", mode="before")
    @classmethod
    def normalize_diagnostic_feedback(cls, value: Any) -> list[str]:
        """Normalize diagnostic feedback into a list of strings.

        Parameters
        ------------
        value: Any
            Input diagnostic feedback: list of strings, single string, or None.

        Returns
        --------
            list[str]: list object
                Harmonized list of diagnostic feedback strings.
        """
        result: list[str] = []
        if value is None:
            return result
        if isinstance(value, str):
            stripped: str = value.strip()
            if stripped:
                result = [stripped]
            return result
        if isinstance(value, (list, tuple)):
            result = [
                str(item).strip() for item in value if str(item).strip()
            ]
            return result
        str_val: str = str(value).strip()
        if str_val:
            result = [str_val]
        return result

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def normalize_timestamp_str(cls, value: Any) -> str | None:
        """Normalize timestamp input to ISO 8601 formatted string.

        Parameters
        ------------
        value: Any
            Input timestamp value as string, datetime, or None.

        Returns
        --------
            str | None: string or None
                Harmonized ISO 8601 string or None if unassigned.
        """
        result: str | None = None
        if value is None:
            return result
        if isinstance(value, datetime):
            result = value.isoformat()
            return result
        str_val: str = str(value).strip()
        if str_val:
            result = str_val
        return result

    @property
    def role(self) -> str:
        """Provide alias for agent_role matching PROJECT.md interface.

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                Specialist agent role name.
        """
        result: str = self.agent_role
        return result

    @property
    def harness(self) -> str:
        """Provide alias for harness_id matching PROJECT.md interface.

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                Target harness identifier.
        """
        result: str = self.harness_id
        return result



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
            TaskEdge: TaskEdge instance
                Validated task edge instance.
        """
        if self.parent_node_id == self.child_node_id:
            raise ValueError(
                f"Self-loop detected: parent and child node ID is "
                f"{self.parent_node_id}"
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
    event_type: Literal[
        "thinking_delta",
        "token_usage",
        "tool_lifecycle",
        "circuit_breaker",
    ]
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
            NiiVueLayerSpec: NiiVueLayerSpec instance
                Validated layer specification instance.
        """
        if self.cal_min is not None and self.cal_max is not None:
            if self.cal_min > self.cal_max:
                raise ValueError(
                    f"cal_min ({self.cal_min}) cannot exceed "
                    f"cal_max ({self.cal_max})"
                )
        return self


class NiiVueSceneSpec(BaseModel):
    """Declarative scene manifest pushed over WebSocket to local NiiVue viewer.

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
        min_length=1,
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
            Enumeration value representing conversation participant role.
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

    Carries payload data decoupling presentation frontends from core
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


__all__: list[str] = [
    "ChatRole",
    "ChatTurn",
    "ModalityType",
    "NeuriTaskEnvelope",
    "NeuriTaskResult",
    "NiiVueLayerSpec",
    "NiiVueSceneSpec",
    "RemoteArtifact",
    "SanitizedNeuroHeader",
    "SessionEvent",
    "SessionEventType",
    "TaskEdge",
    "TaskNode",
    "TaskState",
    "TelemetryEvent",
]
