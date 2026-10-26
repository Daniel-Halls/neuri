"""Neuroimaging Specialist sub-agent for Neuri.

Focuses on structural (T1w/T2w), functional (fMRI), diffusion (DWI/tractography)
MRI preprocessing and Bayesian Simulation-Based Inference (SBI) convergence.
"""

from neuri.agents.base_agent import BaseSpecialistAgent


class NeuroimagingSpecialistAgent(BaseSpecialistAgent):
    """Specialist sub-agent for MRI processing, registration, and tractography.

    Parameters
    ------------
    None

    Returns
    --------
        NeuroimagingSpecialistAgent: NeuroimagingSpecialistAgent instance
            Constructed neuroimaging specialist agent.
    """

    DEFAULT_PROMPT: str = "You are the Neuri Neuroimaging Specialist."

    def __init__(self) -> None:
        """Initialize Neuroimaging Specialist agent with MRI processing skills.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Initializes agent state.
        """
        super().__init__(
            role_name="neuroimaging_specialist",
            system_prompt=self.DEFAULT_PROMPT,
            skill_ids=[
                "neuroimaging-preproc",
                "fmri-postproc",
                "dwi-tractography",
            ],
            mcp_tools=["neuro_resources", "scholar"],
        )


__all__: list[str] = [
    "NeuroimagingSpecialistAgent",
]
