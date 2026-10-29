"""Core schemas, data models, blackboard, and orchestration for Neuri."""

from typing import Any

from neuri.core.blackboard import (
    ArtifactRegistrationError,
    Blackboard,
    BlackboardError,
    CycleDetectedError,
    InvalidStateTransitionError,
    NodeNotFoundError,
    WorkflowNotFoundError,
)
from neuri.core.config import (
    BudgetConfig,
    ConfigError,
    ConfigManager,
    HarnessRoutingConfig,
    NeuriConfig,
    WorkspaceConfig,
    deep_merge,
    find_project_root,
    init_project_workspace,
    init_workspace,
    load_config,
)
from neuri.core.installer import NeuriInstaller
from neuri.core.paths import PathResolver
from neuri.core.preflight import (
    PreflightCheckResult,
    PreflightValidationError,
    PreflightValidator,
)
from neuri.core.rules import RuleLoader
from neuri.core.schemas import (
    ChatRole,
    ChatTurn,
    ModalityType,
    NeuriTaskEnvelope,
    NeuriTaskResult,
    NiiVueLayerSpec,
    NiiVueSceneSpec,
    RemoteArtifact,
    SanitizedNeuroHeader,
    SessionEvent,
    SessionEventType,
    TaskEdge,
    TaskNode,
    TaskState,
    TelemetryEvent,
)
from neuri.core.telemetry import (
    CircuitBreakerTripped,
    ConsecutiveToolFailureLimitExceeded,
    ModelPricing,
    ModelPricingTable,
    NeuriException,
    NodeTokenLimitExceeded,
    ParsedStreamChunk,
    StreamEventNormalizer,
    StreamingThinkingParser,
    TelemetryConstants,
    TelemetryTap,
    ThinkingParser,
    TokenCostTracker,
    WorkflowCostLimitExceeded,
)


def __getattr__(name: str) -> Any:
    """Lazily resolve orchestrator, session, and slash_commands symbols.

    Prevents circular imports when `neuri.adapters` imports `neuri.core.schemas`.

    Parameters
    ------------
    name: str
        Attribute name requested on `neuri.core`.

    Returns
    --------
        Any: Any object
            Resolved class or object from core submodules.
    """
    if name in ("DAGOrchestrator", "OrchestratorError"):
        from neuri.core import orchestrator

        target: Any = getattr(orchestrator, name)
        return target
    if name == "NeuriSessionEngine":
        from neuri.core.session import NeuriSessionEngine

        return NeuriSessionEngine
    if name in ("SlashCommandResult", "SlashCommandRouter"):
        from neuri.core import slash_commands

        cmd_target: Any = getattr(slash_commands, name)
        return cmd_target
    raise AttributeError(f"module 'neuri.core' has no attribute '{name}'")


__all__: list[str] = [
    "ArtifactRegistrationError",
    "Blackboard",
    "BlackboardError",
    "BudgetConfig",
    "ChatRole",
    "ChatTurn",
    "CircuitBreakerTripped",
    "ConfigError",
    "ConfigManager",
    "ConsecutiveToolFailureLimitExceeded",
    "CycleDetectedError",
    "DAGOrchestrator",
    "HarnessRoutingConfig",
    "InvalidStateTransitionError",
    "ModalityType",
    "ModelPricing",
    "ModelPricingTable",
    "NeuriConfig",
    "NeuriException",
    "NeuriInstaller",
    "NeuriSessionEngine",
    "NeuriTaskEnvelope",
    "NeuriTaskResult",
    "NiiVueLayerSpec",
    "NiiVueSceneSpec",
    "NodeNotFoundError",
    "NodeTokenLimitExceeded",
    "OrchestratorError",
    "ParsedStreamChunk",
    "PathResolver",
    "PreflightCheckResult",
    "PreflightValidationError",
    "PreflightValidator",
    "RemoteArtifact",
    "RuleLoader",
    "SanitizedNeuroHeader",
    "SessionEvent",
    "SessionEventType",
    "SlashCommandResult",
    "SlashCommandRouter",
    "StreamEventNormalizer",
    "StreamingThinkingParser",
    "TaskEdge",
    "TaskNode",
    "TaskState",
    "TelemetryConstants",
    "TelemetryEvent",
    "TelemetryTap",
    "ThinkingParser",
    "TokenCostTracker",
    "WorkflowCostLimitExceeded",
    "WorkflowNotFoundError",
    "WorkspaceConfig",
    "deep_merge",
    "find_project_root",
    "init_project_workspace",
    "init_workspace",
    "load_config",
]
