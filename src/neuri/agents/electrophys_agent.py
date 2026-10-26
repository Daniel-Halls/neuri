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

    DEFAULT_PROMPT: str = (
        "You are the Neuri Electrophysiology Specialist. Your duties:\n"
        "1. Setting up MNE-Python raw pipelines with zero-phase FIR "
        "bandpass and notch filtering.\n"
        "2. Automated bad channel detection via RANSAC or correlation "
        "thresholds.\n"
        "3. High-pass 1 Hz ICA decomposition for ocular and cardiac "
        "artifact removal.\n"
        "4. BEM head model generation, co-registration, and dSPM/sLORETA "
        "source reconstruction."
    )

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
