"""Role-specialized neuroscience agents and scientific manuscript writer for Neuri.

Provides the 6 canonical specialist agents (pipeline_engineer, neuroimaging_specialist,
electrophys_specialist, compute_operator, critic_qa, scientific_writer) and the
Anti-Hallucination Citation Gate.
"""

from neuri.agents.base_agent import BaseSpecialistAgent
from neuri.agents.compute_agent import ComputeOperatorAgent
from neuri.agents.critic_qa_agent import CriticQAAgent
from neuri.agents.electrophys_agent import ElectrophysSpecialistAgent
from neuri.agents.neuroimaging_agent import NeuroimagingSpecialistAgent
from neuri.agents.pipeline_agent import PipelineEngineerAgent
from neuri.agents.writer_agent import (
    ScientificWriterAgent,
    UnverifiedCitationError,
)

__all__: list[str] = [
    "BaseSpecialistAgent",
    "ComputeOperatorAgent",
    "CriticQAAgent",
    "ElectrophysSpecialistAgent",
    "NeuroimagingSpecialistAgent",
    "PipelineEngineerAgent",
    "ScientificWriterAgent",
    "UnverifiedCitationError",
]
