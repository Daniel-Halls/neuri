"""Compute Operator specialist sub-agent for Neuri.

Focuses strictly on remote execution infrastructure: multiplexed SSH,
remote worker bootstrapping, Slurm sbatch wrappers, sacct polling, Apptainer
binding, and detached tmux session management.
"""

from neuri.agents.base_agent import BaseSpecialistAgent


class ComputeOperatorAgent(BaseSpecialistAgent):
    """Specialist sub-agent restricted to remote staging and HPC batch clusters.

    Parameters
    ------------
    None

    Returns
    --------
        ComputeOperatorAgent: ComputeOperatorAgent instance
            Constructed compute operator agent.
    """

    DEFAULT_PROMPT: str = "You are the Neuri Compute Operator."

    def __init__(self) -> None:
        """Initialize Compute Operator specialist agent with remote compute skills.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Initializes agent state.
        """
        super().__init__(
            role_name="compute_operator",
            system_prompt=self.DEFAULT_PROMPT,
            skill_ids=["remote-compute-slurm"],
            mcp_tools=["remote_worker"],
        )


__all__: list[str] = [
    "ComputeOperatorAgent",
]
