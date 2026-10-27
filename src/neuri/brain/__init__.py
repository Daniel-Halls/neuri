"""Neuri Brain Package.

Provides Obsidian-compatible semantic memory, incremental SQLite FTS5 graph
indexing, and progressive disclosure retrieval to maintain ultra-low context
window utilization across Neuri sessions.
"""

from neuri.brain.indexer import BrainIndexer
from neuri.brain.manager import BrainManager
from neuri.brain.parser import BrainParser
from neuri.brain.retriever import BrainRetriever
from neuri.brain.schemas import (
    BrainContextCapsule,
    BrainEntity,
    BrainNote,
    BrainObservation,
    BrainRelation,
    BrainScope,
    BrainSearchResult,
    BrainStats,
    ObservationCategory,
    RelationType,
)

__all__: list[str] = [
    "BrainContextCapsule",
    "BrainEntity",
    "BrainIndexer",
    "BrainManager",
    "BrainNote",
    "BrainObservation",
    "BrainParser",
    "BrainRelation",
    "BrainRetriever",
    "BrainScope",
    "BrainSearchResult",
    "BrainStats",
    "ObservationCategory",
    "RelationType",
]
