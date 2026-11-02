"""Data models for Neuri documentation and pipeline MCP server.

Provides Pydantic schemas for documentation chunks, pipeline metadata,
search results, and MCP tool responses.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DocType = Literal["commands", "functions", "documentation"]


class PipelineMetadata(BaseModel):
    """Metadata describing an indexed neuroimaging pipeline or package.

    Parameters
    ------------
    name: str
        Canonical normalized name of the package (e.g. 'fmriprep').
    display_name: str
        Formatted display name (e.g. 'fMRIPrep').
    aliases: list[str]
        Alternative lookup aliases and synonyms. Defaults to empty list.
    has_commands: bool
        Whether command-line reference documentation is available.
    has_functions: bool
        Whether Python API and function reference documentation is available.
    has_documentation: bool
        Whether general technical documentation is available.
    description: str
        Brief summary of the pipeline or package. Defaults to empty string.

    Returns
    --------
        PipelineMetadata: PipelineMetadata instance
            Constructed pipeline metadata model.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(..., description="Canonical package identifier")
    display_name: str = Field(..., description="Formatted display name")
    aliases: list[str] = Field(
        default_factory=list, description="Lookup aliases"
    )
    has_commands: bool = Field(
        default=False, description="CLI commands documentation available"
    )
    has_functions: bool = Field(
        default=False, description="Python functions documentation available"
    )
    has_documentation: bool = Field(
        default=False, description="General documentation available"
    )
    description: str = Field(
        default="", description="Package overview summary"
    )


class DocChunkRecord(BaseModel):
    """Atomic documentation chunk parsed from a Markdown source file.

    Parameters
    ------------
    pipeline_name: str
        Canonical name of the owning pipeline (e.g. 'fmriprep').
    doc_type: DocType
        Type of documentation ('commands', 'functions', or 'documentation').
    section_title: str
        Heading or section title where this item was found.
    item_name: str
        Identified flag name, function signature, or subsection topic.
    content: str
        Detailed textual description, usage, options, or parameters.
    source_file: str
        Filesystem path to source markdown file. Defaults to empty string.

    Returns
    --------
        DocChunkRecord: DocChunkRecord instance
            Constructed documentation chunk model.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    pipeline_name: str = Field(..., description="Owning pipeline identifier")
    doc_type: DocType = Field(..., description="Documentation classification")
    section_title: str = Field(..., description="Section or heading title")
    item_name: str = Field(..., description="Flag, function, or topic name")
    content: str = Field(..., description="Detailed documentation text")
    source_file: str = Field(
        default="", description="Source file relative path"
    )


class DocSearchResult(BaseModel):
    """Ranked search result item returned from documentation queries.

    Parameters
    ------------
    pipeline: str
        Pipeline or package name.
    doc_type: DocType
        Documentation source type ('commands', 'functions', 'documentation').
    section_title: str
        Parent section title.
    item_name: str
        Item name, flag, or function signature.
    content: str
        Excerpt or full content text.
    score: float
        BM25 search relevance score. Defaults to 0.0.

    Returns
    --------
        DocSearchResult: DocSearchResult instance
            Constructed search result model.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    pipeline: str = Field(..., description="Pipeline name")
    doc_type: DocType = Field(..., description="Doc type")
    section_title: str = Field(..., description="Section title")
    item_name: str = Field(..., description="Item or flag name")
    content: str = Field(..., description="Content text")
    score: float = Field(default=0.0, description="BM25 relevance score")


class DocSearchResponse(BaseModel):
    """Standardized response payload for MCP documentation search tools.

    Parameters
    ------------
    pipeline: str
        Resolved canonical pipeline name.
    doc_type: DocType
        Filtered documentation type.
    query: str
        Original search query string.
    total_results: int
        Total number of returned results.
    results: list[DocSearchResult]
        Ranked list of search result items.
    error: str | None
        Error message if pipeline resolution or search failed. Defaults to None.

    Returns
    --------
        DocSearchResponse: DocSearchResponse instance
            Constructed search response payload.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    pipeline: str = Field(..., description="Target pipeline name")
    doc_type: DocType = Field(..., description="Queried doc type")
    query: str = Field(..., description="Search query")
    total_results: int = Field(default=0, description="Match count")
    results: list[DocSearchResult] = Field(
        default_factory=list, description="Ranked results"
    )
    error: str | None = Field(default=None, description="Error message if any")


__all__: list[str] = [
    "DocChunkRecord",
    "DocSearchResponse",
    "DocSearchResult",
    "DocType",
    "PipelineMetadata",
]
