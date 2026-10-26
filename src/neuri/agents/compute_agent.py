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

    DEFAULT_PROMPT: str = (
        "You are the Neuri Compute Operator. Your scope is strictly limited to:\n"
        "1. SSH connectivity, remote directory management, and neuri_worker.\n"
        "2. Formulating Slurm sbatch wrappers with strict error traps and "
        "status.json updates.\n"
        "3. Managing detached tmux sessions on GPU/multi-core workstations.\n"
        "4. Polling job states via sacct or tmux without stalling chat.\n"
        "5. Ensuring Apptainer container bind mounts correctly map data dirs."
    )

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
