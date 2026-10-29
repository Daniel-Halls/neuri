"""Base specialist agent foundation for role-scoped execution in Neuri.

Provides the abstract agent template defining role identity, specialized system
prompts, Tier-1 skill path injection, Tier-2 MCP tool discovery, and strict
header-only context enforcement.
"""

import json
from pathlib import Path
from typing import Any

from neuri.core.config import NeuriConfig
from neuri.core.paths import PathResolver
from neuri.core.rules import RuleLoader
from neuri.core.schemas import NeuriTaskEnvelope, RemoteArtifact


class BaseSpecialistAgent:
    """Base class for domain-specialized neuroscience agents.

    Parameters
    ------------
    role_name: str
        Canonical role identifier (e.g. 'pipeline_engineer', 'critic_qa').
    system_prompt: str
        Base domain system prompt defining persona and constraints.
    skill_ids: list[str]
        List of Tier-1 neuroscience skill identifiers relevant to this role.
    mcp_tools: list[str]
        List of Tier-2 MCP tool servers scoped to this role.

    Returns
    --------
        BaseSpecialistAgent: BaseSpecialistAgent instance
            Constructed specialist agent foundation.
    """

    def __init__(
        self,
        role_name: str,
        system_prompt: str,
        skill_ids: list[str],
        mcp_tools: list[str],
    ) -> None:
        """Initialize specialist agent persona, skills, and tools.

        Parameters
        ------------
        role_name: str
            Agent role name.
        system_prompt: str
            System prompt instructions.
        skill_ids: list[str]
            Tier-1 skill identifiers.
        mcp_tools: list[str]
            Tier-2 MCP tool IDs.

        Returns
        --------
            None: NoneType object
                Initializes agent state.
        """
        self._role: str = role_name
        self._system_prompt: str = system_prompt
        self._skill_ids: list[str] = skill_ids
        self._mcp_tools: list[str] = mcp_tools

    def get_role_name(self) -> str:
        """Retrieve agent role identifier string.

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                Role identifier string.
        """
        return self._role

    def resolve_skill_paths(self) -> list[str]:
        """Resolve full filesystem directory paths for Tier-1 skill manuals.

        Parameters
        ------------
        None

        Returns
        --------
            list[str]: list object
                List of string paths to resolved skill directories.
        """
        paths: list[str] = []
        for s_id in self._skill_ids:
            resolved: Path | None = PathResolver.resolve_skill_dir(s_id)
            if resolved is not None:
                paths.append(str(resolved))
            else:
                paths.append(s_id)
        return paths

    def resolve_mcp_servers(
        self, workspace_dir: Path | None = None
    ) -> dict[str, dict[str, Any]]:
        """Build MCP server configuration dictionary for the agent's tools.

        Parameters
        ------------
        workspace_dir: Path | None
            Optional workspace directory to discover local MCP config.
            Defaults to None.

        Returns
        --------
            dict[str, dict[str, Any]]: dictionary object
                Mapping of MCP server IDs to stdio command definitions.
        """
        config_path: Path | None = PathResolver.get_default_mcp_config(
            workspace_dir=workspace_dir
        )
        registered_servers: dict[str, Any] = {}
        if config_path is not None and config_path.is_file():
            try:
                raw_data: Any = json.loads(
                    config_path.read_text(encoding="utf-8")
                )
                if isinstance(raw_data, dict):
                    registered_servers = raw_data.get("mcpServers", {})
            except Exception:
                registered_servers = {}

        mcp_map: dict[str, dict[str, Any]] = {}
        module_lookup: dict[str, str] = {
            "remote_worker": "neuri_worker.mcp_server",
            "openneuro": "neuri.mcp_servers.mcp_openneuro",
            "git_forge": "neuri.mcp_servers.mcp_git_forge",
            "scholar": "neuri.mcp_servers.mcp_scholar",
            "neuro_resources": "neuri.mcp_servers.mcp_resources",
        }
        for tool_id in self._mcp_tools:
            if tool_id in registered_servers:
                mcp_map[tool_id] = registered_servers[tool_id]
            else:
                mod_name: str = module_lookup.get(
                    tool_id, f"neuri.mcp_servers.mcp_{tool_id}"
                )
                mcp_map[tool_id] = {
                    "command": "python3",
                    "args": ["-m", mod_name],
                }
        return mcp_map

    def build_envelope(
        self,
        workflow_id: str,
        node_id: str,
        task_instruction: str,
        harness_id: str = "antigravity",
        execution_mode: str = "interactive_pty",
        input_artifacts: list[RemoteArtifact] | None = None,
        config: NeuriConfig | None = None,
        extra_context: str = "",
        model: str | None = None,
    ) -> NeuriTaskEnvelope:
        """Construct a role-scoped NeuriTaskEnvelope for harness execution.

        Parameters
        ------------
        workflow_id: str
            Target workflow session identifier.
        node_id: str
            Current DAG task node identifier.
        task_instruction: str
            Specific actionable instruction for the agent.
        harness_id: str
            Target vendor harness identifier. Defaults to 'antigravity'.
        execution_mode: str
            Execution mode ('interactive_pty', 'headless_json'). Defaults to
            'interactive_pty'.
        input_artifacts: list[RemoteArtifact] | None
            Input remote artifact pointers. Defaults to None.
        config: NeuriConfig | None
            Active configuration model. Defaults to None.
        extra_context: str
            Additional dynamic prompt context. Defaults to empty string.
        model: str | None
            Specific model identifier for harness execution. Defaults to None.

        Returns
        --------
            NeuriTaskEnvelope: NeuriTaskEnvelope instance
                Constructed task execution envelope.
        """
        master_prompt: str = RuleLoader.load_master_prompt()
        rules_text: str = RuleLoader.load_agent_rules(role=self._role)
        prompt_parts: list[str] = []
        if master_prompt:
            prompt_parts.append(master_prompt)
        if self._system_prompt:
            prompt_parts.append(self._system_prompt)
        if rules_text:
            prompt_parts.append(f"Operational Rules:\n{rules_text}")
        if extra_context:
            prompt_parts.append(extra_context)
        full_system_prompt: str = "\n\n".join(prompt_parts)

        token_budget: int = (
            config.budgets.max_node_tokens if config is not None else 64000
        )
        cost_budget: float = (
            config.budgets.max_workflow_cost_usd if config is not None else 10.0
        )
        retries_budget: int = (
            config.budgets.max_node_retries if config is not None else 2
        )

        envelope: NeuriTaskEnvelope = NeuriTaskEnvelope(
            workflow_id=workflow_id,
            node_id=node_id,
            agent_role=self._role,
            harness_id=harness_id,
            execution_mode=execution_mode,
            system_prompt=full_system_prompt,
            task_instruction=task_instruction,
            skill_paths=self.resolve_skill_paths(),
            mcp_servers=self.resolve_mcp_servers(),
            input_artifacts=input_artifacts if input_artifacts else [],
            max_tokens_budget=token_budget,
            max_cost_usd=cost_budget,
            attempt_number=1,
            max_retries=retries_budget,
            model=model,
        )
        return envelope


__all__: list[str] = [
    "BaseSpecialistAgent",
]
