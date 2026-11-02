"""Neuri Documentation MCP Server.

Provides a deterministic Model Context Protocol (MCP) tool server exposing
targeted neuroimaging documentation search across commands.md, functions.md,
and documentation.md via standard JSON-RPC 2.0 stdio streams.
"""

import json
import sys
from typing import Any

from neuri.docs.db.repository import DocsRepository
from neuri.docs.ingest.indexer import DocsIndexer
from neuri.docs.models import DocSearchResult, DocType, PipelineMetadata


class DocsMCPServer:
    """JSON-RPC 2.0 Model Context Protocol server for neuroimaging documentation.

    Parameters
    ------------
    repository: DocsRepository | None
        Underlying database repository. Defaults to None (resolves default DB).

    Returns
    --------
        DocsMCPServer: DocsMCPServer instance
            Constructed server instance.
    """

    def __init__(self, repository: DocsRepository | None = None) -> None:
        """Initialize MCP server and ensure database is populated.

        Parameters
        ------------
        repository: DocsRepository | None
            Database repository instance. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes repository reference and auto-indexes if empty.
        """
        self.repository: DocsRepository = repository or DocsRepository()
        self._ensure_database_ready()

    def _ensure_database_ready(self) -> None:
        """Ensure database exists and contains indexed documentation.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Initializes schema and indexes files if database is empty.
        """
        self.repository.init_db()
        pipelines: list[PipelineMetadata] = self.repository.list_pipelines()
        if not pipelines:
            indexer: DocsIndexer = DocsIndexer(repository=self.repository)
            indexer.index_all()

    def list_supported_pipelines(self) -> dict[str, Any]:
        """List all indexed pipelines and their available documentation types.

        Parameters
        ------------
        None

        Returns
        --------
            dict[str, Any]: dictionary object
                List of registered pipelines with available doc types.
        """
        pipelines: list[PipelineMetadata] = self.repository.list_pipelines()
        formatted: list[dict[str, Any]] = [
            {
                "name": p.name,
                "display_name": p.display_name,
                "aliases": p.aliases,
                "has_commands": p.has_commands,
                "has_functions": p.has_functions,
                "has_documentation": p.has_documentation,
                "description": p.description,
            }
            for p in pipelines
        ]
        response: dict[str, Any] = {
            "total_pipelines": len(formatted),
            "pipelines": formatted,
        }
        return response

    def search_commands(
        self,
        pipeline: str,
        query: str,
        limit: int = 5,
    ) -> dict[str, Any]:
        """Search CLI flags, options, syntax, and batch script configurations.

        Parameters
        ------------
        pipeline: str
            Target pipeline or package name (e.g. 'fmriprep', 'fsl', 'qsiprep').
        query: str
            CLI flag or option query terms (e.g. '--output-spaces', '-t').
        limit: int
            Maximum number of result items to return. Defaults to 5.

        Returns
        --------
            dict[str, Any]: dictionary object
                Filtered commands search response dictionary.
        """
        return self._search_by_type(
            pipeline=pipeline,
            query=query,
            doc_type="commands",
            limit=limit,
        )

    def search_functions(
        self,
        pipeline: str,
        query: str,
        limit: int = 5,
    ) -> dict[str, Any]:
        """Search Python APIs, classes, methods, parameters, and signatures.

        Parameters
        ------------
        pipeline: str
            Target Python package name (e.g. 'nilearn', 'nipype', 'nibabel').
        query: str
            Function or class query terms (e.g. 'fetch_haxby', 'NiftiMasker').
        limit: int
            Maximum number of result items to return. Defaults to 5.

        Returns
        --------
            dict[str, Any]: dictionary object
                Filtered functions search response dictionary.
        """
        return self._search_by_type(
            pipeline=pipeline,
            query=query,
            doc_type="functions",
            limit=limit,
        )

    def search_documentation(
        self,
        pipeline: str,
        query: str,
        limit: int = 5,
    ) -> dict[str, Any]:
        """Search general documentation, workflows, BIDS layouts, and rationale.

        Parameters
        ------------
        pipeline: str
            Target pipeline name (e.g. 'fmriprep', 'xcp_d', 'freesurfer').
        query: str
            Conceptual topic or workflow step (e.g. 'anatomical workflow').
        limit: int
            Maximum number of result items to return. Defaults to 5.

        Returns
        --------
            dict[str, Any]: dictionary object
                Filtered general documentation response dictionary.
        """
        return self._search_by_type(
            pipeline=pipeline,
            query=query,
            doc_type="documentation",
            limit=limit,
        )

    def _search_by_type(
        self,
        pipeline: str,
        query: str,
        doc_type: DocType,
        limit: int,
    ) -> dict[str, Any]:
        """Internal helper to execute type-specific documentation search.

        Parameters
        ------------
        pipeline: str
            Input pipeline name or alias.
        query: str
            Text search query string.
        doc_type: DocType
            Category filter ('commands', 'functions', 'documentation').
        limit: int
            Maximum results.

        Returns
        --------
            dict[str, Any]: dictionary object
                Standardized search response payload.
        """
        canonical: str | None = self.repository.resolve_pipeline_name(pipeline)
        if canonical is None:
            supported: list[str] = [
                p.name for p in self.repository.list_pipelines()
            ]
            error_resp: dict[str, Any] = {
                "error": f"Pipeline '{pipeline}' is not recognized.",
                "supported_pipelines": supported,
                "results": [],
            }
            return error_resp

        results: list[DocSearchResult] = self.repository.search(
            pipeline=canonical,
            query=query,
            doc_type=doc_type,
            limit=limit,
        )

        formatted_results: list[dict[str, Any]] = [
            {
                "section": r.section_title,
                "item": r.item_name,
                "content": r.content,
                "relevance_rank": r.score,
            }
            for r in results
        ]

        response: dict[str, Any] = {
            "pipeline": canonical,
            "doc_type": doc_type,
            "query": query,
            "match_count": len(formatted_results),
            "results": formatted_results,
        }
        return response

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Return MCP tool schemas supported by this documentation server.

        Parameters
        ------------
        None

        Returns
        --------
            list[dict[str, Any]]: list object
                Tool schema specifications compliant with MCP JSON-RPC.
        """
        tools: list[dict[str, Any]] = [
            {
                "name": "search_pipeline_commands",
                "description": (
                    "Search command-line arguments, CLI flags, execution syntax, "
                    "options, and Slurm command configurations for a neuroimaging "
                    "pipeline (e.g. fMRIPrep, QSIPrep, FSL, AFNI, FreeSurfer, "
                    "FastSurfer, XCP-D, Workbench, dcm2niix). Use this EXCLUSIVELY "
                    "when constructing, validating, or editing CLI commands and "
                    "batch scripts."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "pipeline": {
                            "type": "string",
                            "description": "Pipeline or package (e.g. 'fmriprep').",
                        },
                        "query": {
                            "type": "string",
                            "description": "CLI flag name (e.g. '--output-spaces').",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results to return (default: 5).",
                            "default": 5,
                        },
                    },
                    "required": ["pipeline", "query"],
                },
            },
            {
                "name": "search_pipeline_functions",
                "description": (
                    "Search Python APIs, classes, function signatures, methods, "
                    "parameters, and return types for a neuroimaging package "
                    "(e.g. Nilearn, Nipype, Nibabel, BCTnet, SPM, Tedana, Pydeface). "
                    "Use this EXCLUSIVELY when writing or editing Python code "
                    "and script calls."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "pipeline": {
                            "type": "string",
                            "description": "Python package name (e.g. 'nilearn').",
                        },
                        "query": {
                            "type": "string",
                            "description": "Function name (e.g. 'fetch_haxby').",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results to return (default: 5).",
                            "default": 5,
                        },
                    },
                    "required": ["pipeline", "query"],
                },
            },
            {
                "name": "search_pipeline_docs",
                "description": (
                    "Search general technical documentation, algorithm details, "
                    "workflow steps, BIDS directory inputs/outputs, and background "
                    "rationale for a neuroimaging pipeline. Use this EXCLUSIVELY "
                    "when explaining concepts, understanding pipeline stages, "
                    "or checking required input/output file structures."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "pipeline": {
                            "type": "string",
                            "description": "Pipeline name (e.g. 'fmriprep', 'xcp_d').",
                        },
                        "query": {
                            "type": "string",
                            "description": "Conceptual topic or workflow stage.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results to return (default: 5).",
                            "default": 5,
                        },
                    },
                    "required": ["pipeline", "query"],
                },
            },
            {
                "name": "list_supported_pipelines",
                "description": (
                    "List all indexed neuroimaging pipelines and packages, "
                    "indicating which documentation categories (commands, "
                    "functions, documentation) are available for each."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]
        return tools

    def dispatch_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Dispatch incoming tool call by name with arguments.

        Parameters
        ------------
        tool_name: str
            Name of target MCP tool.
        arguments: dict[str, Any]
            Arguments passed to the tool.

        Returns
        --------
            dict[str, Any]: dictionary object
                Result dictionary from the dispatched tool.
        """
        if tool_name == "search_pipeline_commands":
            pipeline: str = str(arguments.get("pipeline", ""))
            query: str = str(arguments.get("query", ""))
            limit: int = int(arguments.get("limit", 5))
            return self.search_commands(
                pipeline=pipeline, query=query, limit=limit
            )

        if tool_name == "search_pipeline_functions":
            pipeline = str(arguments.get("pipeline", ""))
            query = str(arguments.get("query", ""))
            limit = int(arguments.get("limit", 5))
            return self.search_functions(
                pipeline=pipeline, query=query, limit=limit
            )

        if tool_name == "search_pipeline_docs":
            pipeline = str(arguments.get("pipeline", ""))
            query = str(arguments.get("query", ""))
            limit = int(arguments.get("limit", 5))
            return self.search_documentation(
                pipeline=pipeline, query=query, limit=limit
            )

        if tool_name == "list_supported_pipelines":
            return self.list_supported_pipelines()

        raise ValueError(f"Unknown MCP tool: '{tool_name}'")

    def handle_request(self, request_dict: dict[str, Any]) -> dict[str, Any]:
        """Process an incoming JSON-RPC 2.0 request and formulate response.

        Parameters
        ------------
        request_dict: dict[str, Any]
            Raw JSON-RPC request dictionary.

        Returns
        --------
            dict[str, Any]: dictionary object
                JSON-RPC 2.0 response dictionary.
        """
        req_id: Any = request_dict.get("id")
        method: str = str(request_dict.get("method", ""))
        params: dict[str, Any] = request_dict.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "neuri-docs-mcp",
                        "version": "0.1.0",
                    },
                },
            }

        if method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

        if method == "tools/list":
            tools_list: list[dict[str, Any]] = self.get_tool_definitions()
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": tools_list},
            }

        if method == "tools/call":
            tool_name: str = str(params.get("name", ""))
            args: dict[str, Any] = params.get("arguments", {})
            try:
                tool_result: dict[str, Any] = self.dispatch_tool(
                    tool_name, args
                )
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(tool_result, indent=2),
                            }
                        ]
                    },
                }
            except Exception as exc:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32000, "message": str(exc)},
                }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: '{method}'",
            },
        }

    def run_stdio_loop(self) -> None:
        """Run standard I/O JSON-RPC loop until EOF on stdin.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Loops over incoming lines from sys.stdin and writes to sys.stdout.
        """
        for line in sys.stdin:
            line_str: str = line.strip()
            if not line_str:
                continue
            try:
                request: dict[str, Any] = json.loads(line_str)
                response: dict[str, Any] = self.handle_request(request)
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
            except Exception as exc:
                err_resp: dict[str, Any] = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": str(exc)},
                }
                sys.stdout.write(json.dumps(err_resp) + "\n")
                sys.stdout.flush()


def main() -> None:
    """CLI entrypoint for executing documentation MCP server over stdio.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Initializes and executes stdio loop.
    """
    server: DocsMCPServer = DocsMCPServer()
    server.run_stdio_loop()


if __name__ == "__main__":
    main()

__all__: list[str] = [
    "DocsMCPServer",
    "main",
]
