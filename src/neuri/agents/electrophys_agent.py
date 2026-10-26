"""Electrophysiology Specialist sub-agent for Neuri.

Focuses on MNE-Python EEG, MEG, and iEEG preprocessing pipelines, bad-channel
detection, Independent Component Analysis (ICA), and source localization.
"""

from neuri.agents.base_agent import BaseSpecialistAgent


class ElectrophysSpecialistAgent(BaseSpecialistAgent):
    """Specialist sub-agent for EEG/MEG artifact cleaning, filtering, and source.

    Parameters
    ------------
    None

    Returns
    --------
        ElectrophysSpecialistAgent: ElectrophysSpecialistAgent instance
            Constructed electrophysiology specialist agent.
    """

    DEFAULT_PROMPT: str = "You are the Neuri Electrophysiology Specialist."

    def __init__(self) -> None:
        """Initialize Electrophysiology Specialist agent with Tier-1 EEG/MEG skills.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Initializes agent state.
        """
        super().__init__(
            role_name="electrophys_specialist",
            system_prompt=self.DEFAULT_PROMPT,
            skill_ids=["eeg-meg-pipeline"],
            mcp_tools=["scholar", "neuro_resources"],
        )


__all__: list[str] = [
    "ElectrophysSpecialistAgent",
]
