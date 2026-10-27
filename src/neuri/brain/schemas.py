"""Neuri Brain Schemas Module.

Defines Pydantic v2 data models and enumerations for the Obsidian-compatible
semantic memory subsystem, including observation categories, relation types,
entity nodes, notes, context capsules, search results, and vault statistics.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BrainScope(str, Enum):
    """Enumeration of knowledge scopes supported by Neuri Brain.

    Parameters
    ------------
    None

    Returns
    --------
        BrainScope: BrainScope enum member
            Enumeration value representing the memory scope.
    """

    GLOBAL = "global"
    PROJECT = "project"


class ObservationCategory(str, Enum):
    """Standardized categories for atomic observations within Brain notes.

    Parameters
    ------------
    None

    Returns
    --------
        ObservationCategory: ObservationCategory enum member
            Category classification for the observation.
    """

    METHODOLOGY = "methodology"
    FINDING = "finding"
    PARAMETER = "parameter"
    LIMITATION = "limitation"
    DECISION = "decision"
    QA_VERDICT = "qa_verdict"
    HYPOTHESIS = "hypothesis"
    GENERAL = "general"


class RelationType(str, Enum):
    """Semantic relation types connecting Brain entities via WikiLinks.

    Parameters
    ------------
    None

    Returns
    --------
        RelationType: RelationType enum member
            Directed relation edge classification.
    """

    EXTENDS = "extends"
    CONTRASTS_WITH = "contrasts_with"
    USES_METHOD = "uses_method"
    USES_ATLAS = "uses_atlas"
    USES_DATASET = "uses_dataset"
    VALIDATED_BY = "validated_by"
    PART_OF = "part_of"
    APPLIES_TO = "applies_to"
    DERIVED_FROM = "derived_from"
    LINKS_TO = "links_to"


class BrainObservation(BaseModel):
    """Atomic observation statement extracted from a Brain note.

    Parameters
    ------------
    category: ObservationCategory
        Classification category of the observation.
    content: str
        Atomic factual statement without category prefix.
    tags: list[str]
        Inline hashtag labels associated with the observation.
    line_number: int | None
        Source line number in the Markdown file. Defaults to None.

    Returns
    --------
        BrainObservation: BrainObservation instance
            Constructed atomic observation model.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    category: ObservationCategory = Field(
        default=ObservationCategory.GENERAL,
        description="Classification category of the observation",
    )
    content: str = Field(
        ...,
        description="Atomic factual statement",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Inline hashtag labels",
    )
    line_number: int | None = Field(
        default=None,
        description="Source line number in Markdown file",
    )

    @field_validator("content")
    @classmethod
    def validate_content_non_empty(cls, value: str) -> str:
        """Validate that observation content is not empty or whitespace.

        Parameters
        ------------
        value: str
            Raw content string to validate.

        Returns
        --------
            str: string object
                Trimmed observation content string.
        """
        trimmed: str = value.strip()
        if not trimmed:
            raise ValueError("Observation content cannot be empty.")
        return trimmed


class BrainRelation(BaseModel):
    """Directed semantic relationship connecting two Brain entities.

    Parameters
    ------------
    relation_type: RelationType
        Type of relationship.
    target_permalink: str
        Target permalink or WikiLink label.
    target_title: str | None
        Human-readable title of target entity. Defaults to None.
    context_snippet: str | None
        Surrounding context or justification. Defaults to None.

    Returns
    --------
        BrainRelation: BrainRelation instance
            Constructed semantic relation model.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    relation_type: RelationType = Field(
        default=RelationType.LINKS_TO,
        description="Type of directed relationship",
    )
    target_permalink: str = Field(
        ...,
        description="Target permalink or WikiLink title",
    )
    target_title: str | None = Field(
        default=None,
        description="Optional human readable target title",
    )
    context_snippet: str | None = Field(
        default=None,
        description="Surrounding context snippet",
    )

    @field_validator("target_permalink")
    @classmethod
    def validate_target_non_empty(cls, value: str) -> str:
        """Validate target permalink identifier is not empty.

        Parameters
        ------------
        value: str
            Raw target identifier string.

        Returns
        --------
            str: string object
                Trimmed target identifier.
        """
        trimmed: str = value.strip()
        if not trimmed:
            raise ValueError("Target permalink cannot be empty.")
        return trimmed


class BrainEntity(BaseModel):
    """Indexable metadata representing a single Brain note file.

    Parameters
    ------------
    entity_id: str
        Unique permalink identifier or slug for the note.
    scope: BrainScope
        Knowledge scope classification.
    title: str
        Human-readable note title.
    entity_type: str
        Note type tag from frontmatter. Defaults to 'note'.
    file_path: str
        Relative filesystem path within the vault.
    content_sha256: str
        SHA-256 hash of file contents for dirty checking.
    mtime_ns: int
        Filesystem modification time in nanoseconds.
    frontmatter: dict[str, Any]
        Raw parsed YAML frontmatter dictionary.
    summary_excerpt: str
        First paragraph executive summary. Defaults to ''.
    observations_count: int
        Total atomic observations extracted. Defaults to 0.
    relations_count: int
        Total outgoing relationships extracted. Defaults to 0.

    Returns
    --------
        BrainEntity: BrainEntity instance
            Constructed index entity model.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    entity_id: str = Field(..., description="Unique permalink identifier")
    scope: BrainScope = Field(..., description="Scope classification")
    title: str = Field(..., description="Human readable note title")
    entity_type: str = Field(default="note", description="Note type tag")
    file_path: str = Field(..., description="Relative filesystem path")
    content_sha256: str = Field(..., description="Content SHA-256 hash")
    mtime_ns: int = Field(..., description="Modification time in nanoseconds")
    frontmatter: dict[str, Any] = Field(
        default_factory=dict,
        description="Parsed YAML frontmatter dictionary",
    )
    summary_excerpt: str = Field(
        default="",
        description="First paragraph executive summary excerpt",
    )
    observations_count: int = Field(
        default=0,
        description="Count of extracted observations",
    )
    relations_count: int = Field(
        default=0,
        description="Count of extracted relations",
    )


class BrainNote(BaseModel):
    """Full representation of a parsed Obsidian Markdown note.

    Parameters
    ------------
    entity: BrainEntity
        Associated index entity metadata.
    observations: list[BrainObservation]
        List of atomic observations extracted from note.
    relations: list[BrainRelation]
        List of directed relations extracted from note.
    body_prose: str
        Freeform prose and markdown content. Defaults to ''.
    headings: list[str]
        List of section headers present in note.

    Returns
    --------
        BrainNote: BrainNote instance
            Constructed parsed note model.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    entity: BrainEntity = Field(..., description="Associated entity metadata")
    observations: list[BrainObservation] = Field(
        default_factory=list,
        description="Atomic observations",
    )
    relations: list[BrainRelation] = Field(
        default_factory=list,
        description="Directed relations",
    )
    body_prose: str = Field(
        default="",
        description="Freeform prose and markdown content",
    )
    headings: list[str] = Field(
        default_factory=list,
        description="Extracted section headings",
    )


class BrainContextCapsule(BaseModel):
    """Tier-0 progressive disclosure context capsule for LLM prompts.

    Parameters
    ------------
    query: str
        Query or task topic used to generate context.
    entities_matched: list[str]
        List of entity identifiers included in capsule.
    token_estimate: int
        Estimated token consumption of markdown context.
    markdown_context: str
        Compact formatted Markdown string with observations.
    truncated: bool
        Whether output was truncated to fit token budget. Defaults to False.

    Returns
    --------
        BrainContextCapsule: BrainContextCapsule instance
            Constructed context capsule model.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    query: str = Field(..., description="Source query string")
    entities_matched: list[str] = Field(
        default_factory=list,
        description="Entity identifiers matched",
    )
    token_estimate: int = Field(
        ...,
        description="Estimated token consumption",
    )
    markdown_context: str = Field(
        ...,
        description="Compact Markdown context string",
    )
    truncated: bool = Field(
        default=False,
        description="Whether capsule was truncated by token limit",
    )


class BrainSearchResult(BaseModel):
    """Search hit returned by semantic or full-text vault search.

    Parameters
    ------------
    entity_id: str
        Unique permalink identifier.
    title: str
        Human-readable note title.
    scope: BrainScope
        Knowledge scope classification.
    file_path: str
        Relative filesystem path in vault.
    score: float
        Relevance score from search engine.
    summary: str
        Executive summary or matching excerpt.
    observations: list[BrainObservation]
        Matching atomic observations.

    Returns
    --------
        BrainSearchResult: BrainSearchResult instance
            Constructed search result model.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    entity_id: str = Field(..., description="Unique permalink identifier")
    title: str = Field(..., description="Human readable title")
    scope: BrainScope = Field(..., description="Scope classification")
    file_path: str = Field(..., description="Relative filesystem path")
    score: float = Field(..., description="Relevance score")
    summary: str = Field(default="", description="Executive summary")
    observations: list[BrainObservation] = Field(
        default_factory=list,
        description="Matching atomic observations",
    )


class BrainStats(BaseModel):
    """Aggregate statistics for Global and Project Brain vaults.

    Parameters
    ------------
    global_vault_path: str
        Filesystem path to global Obsidian vault.
    project_vault_path: str
        Filesystem path to project Obsidian vault.
    global_notes_count: int
        Total notes in global vault.
    project_notes_count: int
        Total notes in project vault.
    total_observations_count: int
        Total indexed atomic observations.
    total_relations_count: int
        Total indexed relations.
    unresolved_links: list[str]
        List of unresolved forward WikiLink targets.

    Returns
    --------
        BrainStats: BrainStats instance
            Constructed vault statistics model.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    global_vault_path: str = Field(
        ..., description="Path to global Obsidian vault"
    )
    project_vault_path: str = Field(
        ..., description="Path to project Obsidian vault"
    )
    global_notes_count: int = Field(
        ..., description="Total notes in global vault"
    )
    project_notes_count: int = Field(
        ..., description="Total notes in project vault"
    )
    total_observations_count: int = Field(
        ..., description="Total indexed observations"
    )
    total_relations_count: int = Field(
        ..., description="Total indexed relations"
    )
    unresolved_links: list[str] = Field(
        default_factory=list,
        description="Unresolved forward WikiLink targets",
    )


__all__: list[str] = [
    "BrainContextCapsule",
    "BrainEntity",
    "BrainNote",
    "BrainObservation",
    "BrainRelation",
    "BrainScope",
    "BrainSearchResult",
    "BrainStats",
    "ObservationCategory",
    "RelationType",
]
