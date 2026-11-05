"""Model Context Protocol (MCP) server for FSL MNI152 brain atlases.

Provides stdio JSON-RPC interface for querying anatomical parcellations and
white-matter tracts across 20 human FSL atlases without having FSL installed.
"""

from pathlib import Path
import sys
from typing import Any

from neuri.mcp_servers.base_mcp import BaseMCPStdioServer
from neuri.viewer.fsl_atlas import FSLAtlasClient, FSLCoordinateResult
from neuri.viewer.neurosynth import query_neurosynth_coordinates


class FSLAtlasMCPServer(BaseMCPStdioServer):
    """Stdio MCP server exposing deterministic FSL atlas lookup tools.

    Parameters
    ------------
    db_path: Path | None
        Optional explicit path to fsl_atlases.db. Defaults to None.

    Returns
    --------
        FSLAtlasMCPServer: FSLAtlasMCPServer instance
            Constructed MCP server instance.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize MCP server with FSL atlas client instance.

        Parameters
        ------------
        db_path: Path | None
            Database path override. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes MCP server state.
        """
        super().__init__()
        self._client: FSLAtlasClient = FSLAtlasClient(db_path=db_path)

    @property
    def server_name(self) -> str:
        """Return the unique identifier string for this MCP server.

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                Unique MCP server name 'fsl_atlas'.
        """
        name_str: str = "fsl_atlas"
        return name_str

    @property
    def server_version(self) -> str:
        """Return semantic version string for this MCP server.

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                Semantic version string '0.1.0'.
        """
        version_str: str = "0.1.0"
        return version_str

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Declare JSON schemas for tools exposed by this MCP server.

        Parameters
        ------------
        None

        Returns
        --------
            list[dict[str, Any]]: list object
                Tool declarations matching the MCP specification.
        """
        tools: list[dict[str, Any]] = [
            {
                "name": "query_mni_coordinate",
                "description": (
                    "Resolve 3D MNI152 stereotactic coordinates (x, y, z in mm) "
                    "to anatomical brain regions and probabilities across 20 "
                    "human FSL atlases (Harvard-Oxford Cortical/Subcortical, "
                    "Juelich Histological, Cerebellum, Talairach, JHU/XTRACT tracts) "
                    "plus optional Neurosynth functional associations."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "x": {
                            "type": "number",
                            "description": "MNI X in mm (left: -, right: +)",
                        },
                        "y": {
                            "type": "number",
                            "description": "MNI Y in mm (post: -, ant: +)",
                        },
                        "z": {
                            "type": "number",
                            "description": "MNI Z in mm (inf: -, sup: +)",
                        },
                        "atlases": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Optional atlas keys (e.g. "
                                "['HarvardOxford-Cortical'])"
                            ),
                        },
                        "min_probability": {
                            "type": "number",
                            "default": 5.0,
                            "description": "Minimum probability threshold (1-100)",
                        },
                        "include_neurosynth": {
                            "type": "boolean",
                            "default": True,
                            "description": "Include Neurosynth functional terms",
                        },
                    },
                    "required": ["x", "y", "z"],
                },
            },
            {
                "name": "search_fsl_brain_region",
                "description": (
                    "Reverse anatomical lookup: search across 20 human FSL "
                    "atlases by region or tract name (e.g. 'Amygdala', 'Insula', "
                    "'Broca') to retrieve labels and exact MNI152 center-of-gravity "
                    "(x, y, z) coordinates."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Brain structure or tract name substring",
                        },
                        "atlas": {
                            "type": "string",
                            "description": "Optional parent atlas key filter",
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "list_fsl_atlases",
                "description": (
                    "List all 20 bundled human FSL atlases in Neuri's "
                    "offline database with full name, type, and parcel count."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]
        return tools

    def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> Any:
        """Execute a declared FSL atlas tool and return result.

        Parameters
        ------------
        tool_name: str
            Name of tool to execute.
        arguments: dict[str, Any]
            Arguments dictionary for tool execution.

        Returns
        --------
            Any: object
                Tool output dictionary or list.
        """
        if tool_name == "query_mni_coordinate":
            x: float = float(arguments["x"])
            y: float = float(arguments["y"])
            z: float = float(arguments["z"])
            atlas_filter: list[str] | None = arguments.get("atlases")
            min_prob: float = float(arguments.get("min_probability", 5.0))
            include_ns: bool = bool(arguments.get("include_neurosynth", True))

            fsl_res: FSLCoordinateResult = self._client.query_coordinate(
                x=x, y=y, z=z, atlas_filter=atlas_filter, min_prob=min_prob
            )
            response_payload: dict[str, Any] = {
                "x": x,
                "y": y,
                "z": z,
                "fsl_anatomy": fsl_res.to_dict(),
                "summary": fsl_res.to_summary_text(),
            }

            if include_ns:
                ns_res = query_neurosynth_coordinates(x=x, y=y, z=z)
                response_payload["neurosynth"] = ns_res.to_dict()

            return response_payload

        if tool_name == "search_fsl_brain_region":
            query_str: str = str(arguments["query"])
            atlas_arg: str | None = arguments.get("atlas")
            atlas_filter_opt: list[str] | None = (
                [atlas_arg] if atlas_arg else None
            )
            matches = self._client.search_regions(
                query=query_str, atlas_filter=atlas_filter_opt
            )
            return [m.to_dict() for m in matches]

        if tool_name == "list_fsl_atlases":
            return self._client.list_atlases()

        raise ValueError(f"Unknown FSL atlas tool: '{tool_name}'")


def main() -> None:
    """Run the FSL atlas MCP server over standard I/O.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Executes stdio server loop until stdin closes.
    """
    server: FSLAtlasMCPServer = FSLAtlasMCPServer()
    server.run()


if __name__ == "__main__":
    main()
