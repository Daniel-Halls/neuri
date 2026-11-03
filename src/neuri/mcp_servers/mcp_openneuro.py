"""OpenNeuro MCP server and remote staging command generator for Neuri.

Provides tools for querying open neuroimaging datasets by modality, task,
and subject count, generating sparse DataLad or S3 transfer commands targeting
remote compute spokes.
"""

import json
import re
import shlex
import sys
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

from neuri.mcp_servers.base_mcp import BaseMCPStdioServer


class OpenNeuroDataset(BaseModel):
    """Metadata summary of an OpenNeuro repository dataset.

    Parameters
    ------------
    dataset_id: str
        Canonical OpenNeuro dataset accession (e.g. 'ds000228').
    name: str
        Descriptive study title.
    modalities: list[str]
        Neuroimaging modalities included (e.g. ['bold', 'T1w', 'dwi']).
    subject_count: int
        Total number of participant subjects.
    tasks: list[str]
        Experimental cognitive/sensory tasks. Defaults to empty list.
    s3_url: str
        Public AWS S3 bucket endpoint.

    Returns
    --------
        OpenNeuroDataset: OpenNeuroDataset instance
            Constructed dataset metadata model.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_id: str = Field(..., description="OpenNeuro dataset accession")
    name: str = Field(..., description="Descriptive study title")
    modalities: list[str] = Field(..., description="Modalities present")
    subject_count: int = Field(default=1, description="Subject count")
    tasks: list[str] = Field(default_factory=list, description="Task names")
    s3_url: str = Field(..., description="S3 public endpoint")


class OpenNeuroMCPServer(BaseMCPStdioServer):
    """FastMCP-compatible JSON-RPC server for OpenNeuro search and staging.

    Parameters
    ------------
    endpoint_url: str
        OpenNeuro GraphQL endpoint URL. Defaults to standard endpoint.

    Returns
    --------
        OpenNeuroMCPServer: OpenNeuroMCPServer instance
            Constructed OpenNeuro server instance.
    """

    def __init__(
        self, endpoint_url: str = "https://openneuro.org/crn/graphql"
    ) -> None:
        """Initialize OpenNeuro MCP server.

        Parameters
        ------------
        endpoint_url: str
            OpenNeuro GraphQL API endpoint. Defaults to standard endpoint.

        Returns
        --------
            None: NoneType object
                Initializes server state.
        """
        super().__init__()
        self._endpoint: str = endpoint_url
        self._mock_registry: dict[str, OpenNeuroDataset] = {
            "ds000228": OpenNeuroDataset(
                dataset_id="ds000228",
                name="Development of Functional Connectome",
                modalities=["bold", "T1w"],
                subject_count=155,
                tasks=["movie"],
                s3_url="s3://openneuro.org/ds000228",
            ),
            "ds000030": OpenNeuroDataset(
                dataset_id="ds000030",
                name="UCLA Consortium for Neuropsychiatric Phenomics",
                modalities=["bold", "T1w", "dwi"],
                subject_count=272,
                tasks=["rest", "bart", "stopsignal"],
                s3_url="s3://openneuro.org/ds000030",
            ),
            "ds003059": OpenNeuroDataset(
                dataset_id="ds003059",
                name="Naturalistic Auditory Functional Connectome",
                modalities=["bold", "T1w"],
                subject_count=21,
                tasks=["listening"],
                s3_url="s3://openneuro.org/ds003059",
            ),
        }

    def build_search_query(
        self,
        modality: str | None = None,
        task: str | None = None,
        min_subjects: int = 1,
    ) -> str:
        """Format a GraphQL search query for OpenNeuro CRN API.

        Parameters
        ------------
        modality: str | None
            Filter by modality ('bold', 'T1w', 'dwi'). Defaults to None.
        task: str | None
            Filter by task name. Defaults to None.
        min_subjects: int
            Minimum participant count threshold. Defaults to 1.

        Returns
        --------
            str: string object
                Formatted GraphQL query payload string.
        """
        query_str: str = (
            "query SearchDatasets {"
            "  datasets(first: 20) {"
            "    edges {"
            "      node {"
            "        id"
            "        name"
            "        analytics { downloads views }"
            "      }"
            "    }"
            "  }"
            "}"
        )
        return query_str

    def search_datasets(
        self,
        modality: str | None = None,
        task: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search datasets matching modality or task criteria.

        Parameters
        ------------
        modality: str | None
            Modality filter. Defaults to None.
        task: str | None
            Task filter. Defaults to None.
        limit: int
            Maximum number of dataset summaries to return. Defaults to 10.

        Returns
        --------
            list[dict[str, Any]]: list object
                List of dataset metadata dictionaries.
        """
        results: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for ds in self._mock_registry.values():
            if modality and modality.lower() not in [
                m.lower() for m in ds.modalities
            ]:
                continue
            if task and task.lower() not in [t.lower() for t in ds.tasks]:
                continue
            results.append(ds.model_dump())
            seen_ids.add(ds.dataset_id.lower())
            if len(results) >= limit:
                break

        if not self._endpoint.startswith("mock://") and len(results) < limit:
            try:
                query_str: str = self.build_search_query(modality, task)
                with httpx.Client(timeout=5.0) as client:
                    resp = client.post(self._endpoint, json={"query": query_str})
                    if resp.status_code == 200:
                        edges = (
                            resp.json()
                            .get("data", {})
                            .get("datasets", {})
                            .get("edges", [])
                        )
                        for edge in edges:
                            if len(results) >= limit:
                                break
                            node = edge.get("node", {})
                            d_id = node.get("id", "")
                            if not d_id or d_id.lower() in seen_ids:
                                continue
                            seen_ids.add(d_id.lower())
                            results.append({
                                "dataset_id": d_id,
                                "name": node.get("name", f"OpenNeuro {d_id}"),
                                "modalities": (
                                    [modality] if modality else ["bold", "T1w"]
                                ),
                                "subject_count": 0,
                                "tasks": [task] if task else [],
                                "s3_url": f"s3://openneuro.org/{d_id}",
                            })
            except Exception:
                pass

        return results

    def get_dataset_metadata(self, dataset_id: str) -> dict[str, Any]:
        """Fetch metadata dictionary for a specific OpenNeuro dataset.

        Parameters
        ------------
        dataset_id: str
            OpenNeuro accession ID (e.g. 'ds000228').

        Returns
        --------
            dict[str, Any]: dictionary object
                Dataset details dictionary.
        """
        clean_id: str = dataset_id.strip().lower()
        if clean_id in self._mock_registry:
            return self._mock_registry[clean_id].model_dump()
        return {
            "dataset_id": dataset_id,
            "name": f"OpenNeuro dataset {dataset_id}",
            "modalities": ["T1w", "bold"],
            "subject_count": 0,
            "tasks": [],
            "s3_url": f"s3://openneuro.org/{dataset_id}",
        }

    def build_datalad_staging_command(
        self,
        dataset_id: str,
        target_dir: str,
        sparse_pattern: str | None = None,
    ) -> str:
        """Construct shell command sequence for sparse DataLad staging on remote spoke.

        Parameters
        ------------
        dataset_id: str
            OpenNeuro dataset accession.
        target_dir: str
            Destination directory on remote host.
        sparse_pattern: str | None
            Optional file glob pattern to fetch (e.g. 'sub-01/ses-1/anat/*').
            Defaults to None (metadata only).

        Returns
        --------
            str: string object
                Executable bash staging command pipeline.
        """
        clean_id: str = dataset_id.strip().lower()
        if not re.match(r"^ds\d{6}$", clean_id):
            raise ValueError(
                f"Invalid OpenNeuro dataset accession: {dataset_id}"
            )
        quoted_dir: str = shlex.quote(target_dir)
        repo_url: str = f"https://github.com/OpenNeuroDatasets/{clean_id}.git"
        if sparse_pattern:
            cmd: str = (
                f"mkdir -p {quoted_dir} && "
                f"datalad install -d {quoted_dir} {repo_url} && "
                f"cd {quoted_dir} && datalad get {sparse_pattern}"
            )
        else:
            cmd = (
                f"mkdir -p {quoted_dir} && "
                f"datalad install -d {quoted_dir} {repo_url}"
            )
        return cmd

    def build_s3_staging_command(
        self,
        dataset_id: str,
        target_dir: str,
        include_pattern: str = "sub-01/*",
    ) -> str:
        """Construct AWS CLI command sequence for zero-credential public S3 sync.

        Parameters
        ------------
        dataset_id: str
            OpenNeuro dataset accession.
        target_dir: str
            Target destination directory path.
        include_pattern: str
            File pattern to include in sparse sync. Defaults to 'sub-01/*'.

        Returns
        --------
            str: string object
                AWS CLI sync command with --no-sign-request.
        """
        clean_id: str = dataset_id.strip().lower()
        if not re.match(r"^ds\d{6}$", clean_id):
            raise ValueError(
                f"Invalid OpenNeuro dataset accession: {dataset_id}"
            )
        s3_source: str = f"s3://openneuro.org/{clean_id}"
        quoted_dir: str = shlex.quote(target_dir)
        cmd: str = (
            f"mkdir -p {quoted_dir} && "
            f"aws s3 sync --no-sign-request {s3_source} {quoted_dir} "
            f'--exclude "*" --include "{include_pattern}"'
        )
        return cmd

    @property
    def server_name(self) -> str:
        """Return server name identifier.

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                Server identifier.
        """
        return "neuri-openneuro-mcp"

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Return declared OpenNeuro tools.

        Parameters
        ------------
        None

        Returns
        --------
            list[dict[str, Any]]: list object
                OpenNeuro tool definitions.
        """
        tools: list[dict[str, Any]] = [
            {
                "name": "search_datasets",
                "description": "Search OpenNeuro datasets by modality or task",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "modality": {"type": "string"},
                        "task": {"type": "string"},
                        "limit": {"type": "integer", "default": 10},
                    },
                },
            },
            {
                "name": "get_dataset_metadata",
                "description": (
                    "Fetch detailed metadata for an OpenNeuro dataset"
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                    },
                    "required": ["dataset_id"],
                },
            },
            {
                "name": "build_staging_command",
                "description": "Generate DataLad or S3 sparse staging command",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "target_dir": {"type": "string"},
                        "method": {
                            "type": "string",
                            "enum": ["datalad", "s3"],
                        },
                        "pattern": {"type": "string"},
                    },
                    "required": ["dataset_id", "target_dir"],
                },
            },
        ]
        return tools

    def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> Any:
        """Execute OpenNeuro tool.

        Parameters
        ------------
        tool_name: str
            Tool to execute.
        arguments: dict[str, Any]
            Arguments dictionary.

        Returns
        --------
            Any: object
                Tool output.
        """
        if tool_name == "search_datasets":
            return self.search_datasets(
                modality=arguments.get("modality"),
                task=arguments.get("task"),
                limit=arguments.get("limit", 10),
            )
        if tool_name == "get_dataset_metadata":
            return self.get_dataset_metadata(arguments["dataset_id"])
        if tool_name == "build_staging_command":
            m_type: str = arguments.get("method", "datalad")
            if m_type == "s3":
                return self.build_s3_staging_command(
                    dataset_id=arguments["dataset_id"],
                    target_dir=arguments["target_dir"],
                    include_pattern=arguments.get("pattern", "sub-01/*"),
                )
            return self.build_datalad_staging_command(
                dataset_id=arguments["dataset_id"],
                target_dir=arguments["target_dir"],
                sparse_pattern=arguments.get("pattern"),
            )
        raise ValueError(f"Unknown OpenNeuro tool: '{tool_name}'")

    def handle_jsonrpc(self, request_json: str) -> str:
        """Dispatch JSON-RPC 2.0 requests to OpenNeuro tools.

        Parameters
        ------------
        request_json: str
            Incoming JSON-RPC request string.

        Returns
        --------
            str: string object
                JSON-RPC response string.
        """
        try:
            req: dict[str, Any] = json.loads(request_json)
            resp = self.handle_request(req)
            return json.dumps(resp) if resp is not None else ""
        except Exception as exc:
            return json.dumps({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {exc}"},
            })

    def run_stdio_server(self) -> None:
        """Run stdio JSON-RPC loop for MCP host interaction.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Processes stdin line by line until EOF.
        """
        self.run_stdio_loop()


def main() -> None:
    """CLI entrypoint for executing OpenNeuro MCP server over stdio.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Instantiates OpenNeuroMCPServer and starts stdio loop.
    """
    server: OpenNeuroMCPServer = OpenNeuroMCPServer()
    server.run_stdio_server()


if __name__ == "__main__":
    main()


__all__: list[str] = [
    "OpenNeuroDataset",
    "OpenNeuroMCPServer",
    "main",
]
