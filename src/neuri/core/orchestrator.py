"""DAG Orchestrator and Multi-Agent Execution Engine for Neuri.

Coordinates DAG topological traversal, pre-flight validation, multi-vendor
harness dispatch, bounded auto-retries (N=2), circuit breaker recovery, and
human operator escalation in SQLite WAL Blackboard.
"""

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import uuid

import yaml

from neuri.adapters.base import BaseHarnessAdapter
from neuri.adapters.registry import AdapterRegistry
from neuri.core.blackboard import Blackboard
from neuri.core.preflight import PreflightCheckResult, PreflightValidator
from neuri.core.schemas import (
    NeuriTaskEnvelope,
    NeuriTaskResult,
    RemoteArtifact,
    TaskEdge,
    TaskNode,
    TaskState,
    TelemetryEvent,
)


class OrchestratorError(Exception):
    """Exception raised when workflow orchestration fails.

    Parameters
    ------------
    message: str
        Explanatory error message.

    Returns
    --------
        OrchestratorError: OrchestratorError instance
            Constructed exception object.
    """

    def __init__(self, message: str) -> None:
        """Initialize orchestrator exception.

        Parameters
        ------------
        message: str
            Descriptive error message.

        Returns
        --------
            None: NoneType object
                Initializes exception state.
        """
        super().__init__(message)
        self.message: str = message


class DAGOrchestrator:
    """Multi-agent DAG planner, pre-flight validator, and execution coordinator.

    Ties together the SQLite WAL Blackboard, PreflightValidator, and
    AdapterRegistry to execute neuroscience research workflows with
    fault tolerance and bounded retries.

    Parameters
    ------------
    blackboard: Blackboard
        Persistent SQLite WAL state store.
    adapter_registry: AdapterRegistry | None
        Harness adapter registry. Defaults to new AdapterRegistry.
    preflight_validator: PreflightValidator | None
        Zero-token pre-flight validator. Defaults to new PreflightValidator.
    skills_index_path: Path | None
        Path to skills/index.yaml catalog. Defaults to 'skills/index.yaml'.

    Returns
    --------
        DAGOrchestrator: DAGOrchestrator instance
            Constructed orchestrator engine.
    """

    def __init__(
        self,
        blackboard: Blackboard,
        adapter_registry: AdapterRegistry | None = None,
        preflight_validator: PreflightValidator | None = None,
        skills_index_path: Path | None = None,
    ) -> None:
        """Initialize DAG orchestrator with core dependencies.

        Parameters
        ------------
        blackboard: Blackboard
            Target SQLite Blackboard instance.
        adapter_registry: AdapterRegistry | None
            Harness registry instance. Defaults to None.
        preflight_validator: PreflightValidator | None
            Pre-flight validator. Defaults to None.
        skills_index_path: Path | None
            Catalog file path. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes orchestrator state.
        """
        self._blackboard: Blackboard = blackboard
        self._registry: AdapterRegistry = (
            adapter_registry if adapter_registry is not None else AdapterRegistry()
        )
        self._validator: PreflightValidator = (
            preflight_validator
            if preflight_validator is not None
            else PreflightValidator(catalog_path=skills_index_path)
        )
        self._catalog_path: Path = (
            skills_index_path
            if skills_index_path is not None
            else Path("skills/index.yaml")
        )

    def plan_workflow_from_prompt(
        self, prompt: str, workflow_id: str | None = None
    ) -> str:
        """Analyze user prompt, identify skill matches, and build an initial DAG.

        Parameters
        ------------
        prompt: str
            Natural language research instruction from user.
        workflow_id: str | None
            Optional workflow ID override. Defaults to generated ID.

        Returns
        --------
            str: string object
                Identifier of registered workflow in Blackboard.
        """
        wf_id: str = (
            workflow_id
            if workflow_id is not None
            else f"wf_{uuid.uuid4().hex[:12]}"
        )
        self._blackboard.create_workflow(
            workflow_id=wf_id,
            description=f"Generated from prompt: {prompt[:80]}",
        )

        matched_skills: list[str] = self._match_skills_from_prompt(prompt)
        if not matched_skills:
            matched_skills = ["bids-standard"]

        prev_node_id: str | None = None
        for idx, skill_id in enumerate(matched_skills, start=1):
            node_id: str = f"node_{wf_id}_{idx}_{skill_id.replace('-', '_')}"
            envelope: NeuriTaskEnvelope = NeuriTaskEnvelope(
                workflow_id=wf_id,
                node_id=node_id,
                agent_role="neuroimaging_specialist",
                harness_id="agy",
                execution_mode="headless_json",
                system_prompt="You are a neuroimaging specialist.",
                task_instruction=f"Execute {skill_id} for: {prompt}",
                skill_paths=[skill_id],
                max_tokens_budget=64000,
                max_cost_usd=2.00,
                attempt_number=1,
                max_retries=2,
            )
            node: TaskNode = TaskNode(
                node_id=node_id,
                workflow_id=wf_id,
                agent_role="neuroimaging_specialist",
                harness_id="agy",
                state=TaskState.PENDING,
                attempt=0,
                max_retries=2,
                envelope=envelope,
            )
            self._blackboard.register_node(node)

            if prev_node_id is not None:
                edge: TaskEdge = TaskEdge(
                    parent_node_id=prev_node_id,
                    child_node_id=node_id,
                    workflow_id=wf_id,
                )
                self._blackboard.register_edge(edge)
            prev_node_id = node_id

        return wf_id

    def _match_skills_from_prompt(self, prompt: str) -> list[str]:
        """Scan catalog triggers against user prompt to select relevant skills.

        Parameters
        ------------
        prompt: str
            Raw prompt text.

        Returns
        --------
            list[str]: list object
                Ordered list of matched skill identifiers.
        """
        prompt_lower: str = prompt.lower()
        matched: list[str] = []

        if not self._catalog_path.is_file():
            # Fallback keyword matching
            if "bids" in prompt_lower or "nifti" in prompt_lower:
                matched.append("bids-standard")
            if "bet" in prompt_lower or "brain extraction" in prompt_lower:
                matched.append("neuroimaging-preproc")
            if "glm" in prompt_lower or "bold" in prompt_lower:
                matched.append("fmri-postproc")
            return matched

        try:
            content: str = self._catalog_path.read_text(encoding="utf-8")
            data: dict[str, Any] = yaml.safe_load(content) or {}
            skills_list: list[dict[str, Any]] = data.get("skills", [])
            for sk in skills_list:
                s_id: str = str(sk.get("id", ""))
                triggers: list[str] = [
                    str(t).lower() for t in sk.get("triggers", [])
                ]
                for trigger in triggers:
                    if trigger in prompt_lower:
                        if s_id not in matched:
                            matched.append(s_id)
                        break
        except Exception:
            pass

        return matched

    async def execute_ready_nodes(
        self,
        workflow_id: str,
        on_event: Callable[[TelemetryEvent], None] | None = None,
        timeout_seconds: float = 300.0,
    ) -> list[NeuriTaskResult]:
        """Fetch and execute all topological ready nodes for a workflow.

        Parameters
        ------------
        workflow_id: str
            Target workflow identifier.
        on_event: Callable[[TelemetryEvent], None] | None
            Optional telemetry streaming callback. Defaults to None.
        timeout_seconds: float
            Subprocess execution timeout. Defaults to 300.0.

        Returns
        --------
            list[NeuriTaskResult]: list object
                Execution results for all ready nodes processed in this step.
        """
        ready_nodes: list[TaskNode] = self._blackboard.get_ready_nodes(
            workflow_id
        )
        results: list[NeuriTaskResult] = []

        for node in ready_nodes:
            res: NeuriTaskResult = await self._execute_single_node(
                node=node,
                on_event=on_event,
                timeout_seconds=timeout_seconds,
            )
            results.append(res)

        return results

    async def _execute_single_node(
        self,
        node: TaskNode,
        on_event: Callable[[TelemetryEvent], None] | None = None,
        timeout_seconds: float = 300.0,
    ) -> NeuriTaskResult:
        """Execute a single task node with pre-flight check and retry handling.

        Parameters
        ------------
        node: TaskNode
            Task node to execute.
        on_event: Callable[[TelemetryEvent], None] | None
            Telemetry event callback. Defaults to None.
        timeout_seconds: float
            Timeout for subprocess. Defaults to 300.0.

        Returns
        --------
            NeuriTaskResult: NeuriTaskResult instance
                Final execution result.
        """
        # 1. Deterministic pre-flight check
        self._blackboard.update_node_state(
            node.node_id, TaskState.PREFLIGHT_CHECK
        )
        preflight_res: PreflightCheckResult = self._validator.validate_envelope(
            node.envelope
        )
        if not preflight_res.passed:
            err_summary: str = "; ".join(preflight_res.errors)
            self._blackboard.update_node_state(
                node.node_id,
                TaskState.WAITING_OPERATOR,
                diagnostic_feedback=f"Pre-flight failed: {err_summary}",
                summary_result=f"Blocked by pre-flight: {err_summary}",
            )
            fail_res: NeuriTaskResult = NeuriTaskResult(
                node_id=node.node_id,
                success=False,
                exit_code=1,
                summary=f"Pre-flight validation failed: {err_summary}",
                error_message=err_summary,
            )
            return fail_res

        # 2. Dispatch to harness
        self._blackboard.update_node_state(node.node_id, TaskState.RUNNING)
        try:
            adapter: BaseHarnessAdapter = self._registry.get_adapter(
                node.harness_id
            )
        except Exception as exc:
            self._blackboard.update_node_state(
                node.node_id,
                TaskState.WAITING_OPERATOR,
                diagnostic_feedback=f"Harness resolution failed: {exc}",
            )
            harness_fail: NeuriTaskResult = NeuriTaskResult(
                node_id=node.node_id,
                success=False,
                exit_code=127,
                summary=f"Unknown harness: {node.harness_id}",
                error_message=str(exc),
            )
            return harness_fail

        exec_res: NeuriTaskResult = await adapter.execute(
            envelope=node.envelope,
            on_event=on_event,
            timeout_seconds=timeout_seconds,
            blackboard=self._blackboard,
        )

        # 3. Handle outcome
        if exec_res.success:
            self._blackboard.update_node_state(
                node.node_id,
                TaskState.COMPLETED,
                summary_result=exec_res.summary,
            )
            for art in exec_res.artifacts_emitted:
                try:
                    self._blackboard.register_artifact(art)
                except Exception:
                    pass
            return exec_res

        # 4. Handle failure with bounded retries (N=2)
        current_attempt: int = node.attempt + 1
        if current_attempt < node.max_retries:
            new_envelope = node.envelope.model_copy(
                update={
                    "attempt_number": current_attempt + 1,
                    "diagnostic_feedback": exec_res.error_message,
                }
            )
            self._blackboard.update_node_state(
                node.node_id,
                TaskState.RETRYING,
                diagnostic_feedback=exec_res.error_message,
                summary_result=f"Retrying (attempt {current_attempt + 1})",
            )
            # Revert to PENDING so next cycle re-executes with updated attempt
            self._blackboard.update_node_state(
                node.node_id,
                TaskState.PENDING,
            )
        else:
            self._blackboard.update_node_state(
                node.node_id,
                TaskState.WAITING_OPERATOR,
                diagnostic_feedback=(
                    f"Retry budget exhausted ({node.max_retries} attempts). "
                    f"Last error: {exec_res.error_message}"
                ),
                summary_result=f"Paused in WAITING_OPERATOR: {exec_res.summary}",
            )

        return exec_res

    def retry_node(self, node_id: str) -> bool:
        """Reset a node from WAITING_OPERATOR or FAILED back to PENDING.

        Parameters
        ------------
        node_id: str
            Target node identifier.

        Returns
        --------
            bool: boolean object
                True if node was successfully reset, False otherwise.
        """
        node: TaskNode | None = self._blackboard.get_node(node_id)
        if node is None:
            return False

        if node.state in (
            TaskState.WAITING_OPERATOR,
            TaskState.FAILED,
            TaskState.RETRYING,
        ):
            self._blackboard.update_node_state(
                node_id,
                TaskState.PENDING,
                diagnostic_feedback="Operator manual retry requested",
            )
            return True
        return False

    def cancel_node(self, node_id: str) -> bool:
        """Transition a node to CANCELLED state.

        Parameters
        ------------
        node_id: str
            Target node identifier.

        Returns
        --------
            bool: boolean object
                True if node was cancelled, False otherwise.
        """
        node: TaskNode | None = self._blackboard.get_node(node_id)
        if node is None:
            return False

        self._blackboard.update_node_state(
            node_id,
            TaskState.CANCELLED,
            summary_result="Cancelled by operator",
        )
        return True


__all__: list[str] = [
    "DAGOrchestrator",
    "OrchestratorError",
]
