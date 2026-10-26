"""Pipeline Engineer specialist sub-agent for Neuri.

Focuses on BIDS dataset validation, modular Snakemake/Bash workflow generation,
directory tree organization, and reproducible preprocessing orchestration.
"""

from neuri.agents.base_agent import BaseSpecialistAgent


class PipelineEngineerAgent(BaseSpecialistAgent):
    """Specialist sub-agent responsible for data pipelines and BIDS compliance.

    Parameters
    ------------
    None

    Returns
    --------
        PipelineEngineerAgent: PipelineEngineerAgent instance
            Constructed pipeline engineer agent.
    """

    DEFAULT_PROMPT: str = (
        "You are the Neuri Pipeline Engineer. Your responsibilities include:\n"
        "1. Validating and enforcing BIDS dataset hierarchies and naming "
        "conventions.\n"
        "2. Authoring modular, reproducible Snakemake, Bash, and Python "
        "workflow scripts.\n"
        "3. Ensuring containerized tool invocations bind appropriate "
        "directories.\n"
        "4. Never hallucinating directory structures or executing raw "
        "destructive commands."
    )

    def __init__(self) -> None:
        """Initialize Pipeline Engineer specialist agent with Tier-1 BIDS skills.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Initializes agent state.
        """
        super().__init__(
            role_name="pipeline_engineer",
            system_prompt=self.DEFAULT_PROMPT,
            skill_ids=["bids-standard"],
            mcp_tools=["openneuro", "git_forge", "neuro_resources"],
        )


__all__: list[str] = [
    "PipelineEngineerAgent",
]
