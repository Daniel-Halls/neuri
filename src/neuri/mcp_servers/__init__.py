"""Ecosystem FastMCP servers and neuroimaging tool bridges for Neuri.

Provides standard JSON-RPC 2.0 stdio tool servers for OpenNeuro querying,
Git forge repository integration, scholarly literature DOI verification, and
stereotaxic template/atlas resource catalogs.
"""

from neuri.mcp_servers.mcp_git_forge import GitForgeMCPServer, GitRepository
from neuri.mcp_servers.mcp_openneuro import OpenNeuroDataset, OpenNeuroMCPServer
from neuri.mcp_servers.mcp_resources import (
    AtlasInfo,
    NeuroResourceRegistry,
    TemplateSpaceInfo,
)
from neuri.mcp_servers.mcp_scholar import ScholarMCPServer, VerifiedCitation

__all__: list[str] = [
    "AtlasInfo",
    "GitForgeMCPServer",
    "GitRepository",
    "NeuroResourceRegistry",
    "OpenNeuroDataset",
    "OpenNeuroMCPServer",
    "ScholarMCPServer",
    "TemplateSpaceInfo",
    "VerifiedCitation",
]
