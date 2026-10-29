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
from neuri.agents.base_agent import BaseSpecialistAgent
from neuri.agents.compute_agent import ComputeOperatorAgent
from neuri.agents.critic_qa_agent import CriticQAAgent
from neuri.agents.electrophys_agent import ElectrophysSpecialistAgent
from neuri.agents.neuroimaging_agent import NeuroimagingSpecialistAgent
from neuri.agents.pipeline_agent import PipelineEngineerAgent
from neuri.agents.writer_agent import ScientificWriterAgent
from neuri.core.blackboard import Blackboard
from neuri.core.config import NeuriConfig
from neuri.core.paths import PathResolver
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

    SKILL_ROLE_MAP: dict[str, str] = {
        "bids-standard": "neuroimaging_specialist",
        "neuroimaging-preproc": "neuroimaging_specialist",
        "fmri-postproc": "neuroimaging_specialist",
        "dwi-tractography": "neuroimaging_specialist",
        "eeg-meg-pipeline": "electrophys_specialist",
        "remote-compute-slurm": "compute_operator",
        "scientific-writing-neuro": "scientific_writer",
        "scientific-writer": "scientific_writer",
        "researcher-mode": "coordinator",
        "notebooklm": "scientific_writer",
    }

    def __init__(
        self,
        blackboard: Blackboard,
        config: NeuriConfig | None = None,
        adapter_registry: AdapterRegistry | None = None,
        preflight_validator: PreflightValidator | None = None,
        skills_index_path: Path | None = None,
    ) -> None:
        """Initialize DAG orchestrator with core dependencies.

        Parameters
        ------------
        blackboard: Blackboard
            Target SQLite Blackboard instance.
        config: NeuriConfig | None
            Two-tier configuration. Defaults to None (empty NeuriConfig).
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
        self._config: NeuriConfig = config if config is not None else NeuriConfig()
        self._registry: AdapterRegistry = (
            adapter_registry if adapter_registry is not None else AdapterRegistry()
        )
        catalog: Path = (
            skills_index_path
            if skills_index_path is not None
            else PathResolver.get_default_skills_index()
        )
        self._catalog_path: Path = catalog
        self._validator: PreflightValidator = (
            preflight_validator
            if preflight_validator is not None
            else PreflightValidator(catalog_path=catalog)
        )
        self._critic_agent: CriticQAAgent = CriticQAAgent()
        self._specialist_agents: dict[str, BaseSpecialistAgent] = {
            "coordinator": BaseSpecialistAgent(
                role_name="coordinator",
                system_prompt="You are the Neuri Coordinator.",
                skill_ids=[],
                mcp_tools=[],
            ),
            "pipeline_engineer": PipelineEngineerAgent(),
            "neuroimaging_specialist": NeuroimagingSpecialistAgent(),
            "electrophys_specialist": ElectrophysSpecialistAgent(),
            "compute_operator": ComputeOperatorAgent(),
            "critic_qa": self._critic_agent,
            "scientific_writer": ScientificWriterAgent(),
        }

    def _resolve_specialist_agent(
        self, agent_role: str
    ) -> BaseSpecialistAgent:
        """Retrieve the domain specialist agent for a given role name.

        Parameters
        ------------
        agent_role: str
            Canonical agent role identifier.

        Returns
        --------
            BaseSpecialistAgent: BaseSpecialistAgent instance
                Corresponding domain specialist agent.
        """
        agent: BaseSpecialistAgent = self._specialist_agents.get(
            agent_role, self._specialist_agents["coordinator"]
        )
        return agent

    @property
    def registry(self) -> AdapterRegistry:
        """Provide access to the initialized adapter registry.

        Parameters
        ------------
        None

        Returns
        --------
            AdapterRegistry: AdapterRegistry instance
                Underlying adapter registry.
        """
        reg: AdapterRegistry = self._registry
        return reg

    def resolve_active_model(
        self, harness_id: str | None = None
    ) -> str | None:
        """Resolve a valid model dynamically from the target harness.

        If a model is configured and valid for the harness (or the harness
        cannot be queried), returns the configured model. Otherwise returns
        the first available model reported by the harness.

        Parameters
        ------------
        harness_id: str | None
            Target harness identifier. Defaults to active default_harness.

        Returns
        --------
            str | None: string or None
                Resolved model identifier from the harness, or None.
        """
        target_h: str = (
            harness_id
            if harness_id is not None
            else getattr(self._config.project, "default_harness", "agy")
        )
        configured: str | None = self._config.project.default_model
        try:
            avail_models: list[str] = self._registry.get_models_for_harness(
                target_h
            )
        except Exception:
            avail_models = []

        if avail_models:
            if configured and configured in avail_models:
                return configured
            return avail_models[0]
        return configured

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
            prompt=prompt,
        )

        active_harness: str = getattr(
            self._config.project, "default_harness", "agy"
        )
        active_model: str | None = self.resolve_active_model(active_harness)

        matched_skills: list[str] = self._match_skills_from_prompt(prompt)
        if not matched_skills:
            node_id: str = f"node_{wf_id}_1_task"
            agent_role: str = "coordinator"
            route = self._config.harness_routing.get(agent_role)
            harness_id: str = active_harness
            exec_mode: str = route.mode if route is not None else "headless_json"
            model_id: str | None = active_model
            specialist: BaseSpecialistAgent = self._resolve_specialist_agent(
                agent_role
            )
            base_env: NeuriTaskEnvelope = specialist.build_envelope(
                workflow_id=wf_id,
                node_id=node_id,
                task_instruction=prompt,
                harness_id=harness_id,
                execution_mode=exec_mode,
                config=self._config,
                model=model_id,
            )
            envelope: NeuriTaskEnvelope = base_env.model_copy(
                update={"skill_paths": []}
            )
            node: TaskNode = TaskNode(
                node_id=node_id,
                workflow_id=wf_id,
                agent_role=agent_role,
                harness_id=harness_id,
                model=model_id,
                state=TaskState.PENDING,
                attempt=0,
                max_retries=self._config.budgets.max_node_retries,
                envelope=envelope,
            )
            self._blackboard.create_node(node)
            return wf_id

        prev_node_id: str | None = None
        for idx, skill_id in enumerate(matched_skills, start=1):
            node_id: str = f"node_{wf_id}_{idx}_{skill_id.replace('-', '_')}"
            agent_role: str = self.SKILL_ROLE_MAP.get(
                skill_id, "neuroimaging_specialist"
            )
            route = self._config.harness_routing.get(agent_role)
            harness_id: str = active_harness
            exec_mode: str = route.mode if route is not None else "headless_json"
            model_id: str | None = active_model

            resolved_dir: Path | None = PathResolver.resolve_skill_dir(skill_id)
            skill_paths: list[str] = (
                [str(resolved_dir)] if resolved_dir is not None else [skill_id]
            )

            specialist: BaseSpecialistAgent = self._resolve_specialist_agent(
                agent_role
            )
            base_env: NeuriTaskEnvelope = specialist.build_envelope(
                workflow_id=wf_id,
                node_id=node_id,
                task_instruction=(
                    f"Respond directly to the user's request/question "
                    f"(skill context: {skill_id}):\n{prompt}"
                ),
                harness_id=harness_id,
                execution_mode=exec_mode,
                config=self._config,
                model=model_id,
            )
            envelope: NeuriTaskEnvelope = base_env.model_copy(
                update={"skill_paths": skill_paths}
            )
            node: TaskNode = TaskNode(
                node_id=node_id,
                workflow_id=wf_id,
                agent_role=agent_role,
                harness_id=harness_id,
                model=model_id,
                state=TaskState.PENDING,
                attempt=0,
                max_retries=self._config.budgets.max_node_retries,
                envelope=envelope,
            )
            self._blackboard.create_node(node)

            if prev_node_id is not None:
                edge: TaskEdge = TaskEdge(
                    parent_node_id=prev_node_id,
                    child_node_id=node_id,
                    workflow_id=wf_id,
                )
                self._blackboard.add_edge(edge)
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

    async def execute_workflow(
        self,
        workflow_id: str,
        on_event: Callable[[TelemetryEvent], None] | None = None,
        timeout_seconds: float = 300.0,
    ) -> list[NeuriTaskResult]:
        """Execute all ready and dependent DAG nodes wave-by-wave until completion.

        Parameters
        ------------
        workflow_id: str
            Target workflow identifier.
        on_event: Callable[[TelemetryEvent], None] | None
            Optional telemetry streaming callback. Defaults to None.
        timeout_seconds: float
            Subprocess execution timeout per node. Defaults to 300.0.

        Returns
        --------
            list[NeuriTaskResult]: list object
                Aggregated execution results for all processed nodes.
        """
        aggregated: list[NeuriTaskResult] = []
        max_waves: int = 100
        wave: int = 0

        while wave < max_waves:
            wave += 1
            ready: list[TaskNode] = self._blackboard.get_ready_nodes(workflow_id)
            if not ready:
                break

            wave_res: list[NeuriTaskResult] = await self.execute_ready_nodes(
                workflow_id=workflow_id,
                on_event=on_event,
                timeout_seconds=timeout_seconds,
            )
            aggregated.extend(wave_res)

            should_halt: bool = False
            for r in wave_res:
                n: TaskNode | None = self._blackboard.get_node(r.node_id)
                if n is not None and n.state == TaskState.WAITING_OPERATOR:
                    should_halt = True
                    break
            if should_halt:
                break

        return aggregated

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
        if on_event is not None:
            model_info: str = (
                f" ({node.envelope.model})"
                if node.envelope is not None and node.envelope.model
                else ""
            )
            dispatch_ev: TelemetryEvent = TelemetryEvent(
                event_id=f"tevt_{uuid.uuid4().hex[:16]}",
                workflow_id=node.workflow_id,
                node_id=node.node_id,
                harness_id=node.harness_id,
                event_type="raw_stream",
                raw_text=(
                    f"Dispatched node '{node.node_id}' ({node.agent_role}) "
                    f"to harness '{node.harness_id}'{model_info}"
                ),
            )
            on_event(dispatch_ev)
        try:
            adapter: BaseHarnessAdapter = self._registry.get_adapter(
                node.harness_id
            )
            if not adapter.is_available() and node.harness_id != "agy":
                fallback_adapter: BaseHarnessAdapter = (
                    self._registry.get_adapter("agy")
                )
                if fallback_adapter.is_available():
                    adapter = fallback_adapter
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

        if on_event is not None:
            status_txt: str = "completed" if exec_res.success else "failed"
            done_ev: TelemetryEvent = TelemetryEvent(
                event_id=f"tevt_{uuid.uuid4().hex[:16]}",
                workflow_id=node.workflow_id,
                node_id=node.node_id,
                harness_id=node.harness_id,
                event_type="raw_stream",
                raw_text=(
                    f"Node '{node.node_id}' {status_txt} "
                    f"({exec_res.total_tokens:,} tokens, "
                    f"${exec_res.cost_usd:.4f} USD)"
                ),
            )
            on_event(done_ev)

        # 3. Handle outcome via QA_REVIEW and CriticQAAgent
        if exec_res.success:
            for art in exec_res.artifacts_emitted:
                try:
                    self._blackboard.register_artifact(
                        art, workflow_id=node.workflow_id, node_id=node.node_id
                    )
                except Exception:
                    pass
            self._blackboard.update_node_state(
                node.node_id,
                TaskState.QA_REVIEW,
                summary_result=exec_res.summary,
            )
            self._critic_agent.review_node(
                blackboard=self._blackboard,
                node_id=node.node_id,
            )
            return exec_res

        # 4. Handle failure with bounded retries (N=2)
        current_attempt: int = node.attempt + 1
        if current_attempt < node.max_retries:
            new_envelope: NeuriTaskEnvelope = node.envelope.model_copy(
                update={
                    "attempt_number": current_attempt + 1,
                    "diagnostic_feedback": exec_res.error_message,
                }
            )
            self._blackboard.update_node_envelope(node.node_id, new_envelope)
            self._blackboard.update_node_state(
                node.node_id,
                TaskState.RETRYING,
                diagnostic_feedback=exec_res.error_message,
                summary_result=f"Retrying (attempt {current_attempt + 1})",
            )
            # Revert to PENDING so next wave re-executes with updated attempt
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
