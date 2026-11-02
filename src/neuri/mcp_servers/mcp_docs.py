"""MCP Server module exposing neuroimaging documentation tools for Neuri.

Provides stdio JSON-RPC interface for searching CLI commands, Python functions,
and general documentation across 20+ MRI neuroimaging pipelines.
"""

from neuri.docs.server import DocsMCPServer, main

__all__: list[str] = [
    "DocsMCPServer",
    "main",
]

if __name__ == "__main__":
    main()

