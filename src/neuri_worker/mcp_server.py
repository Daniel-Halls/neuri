"""Remote stdio FastMCP server executed on remote compute spokes.

Exposes deterministic neuroimaging header inspection, BIDS validation, and
artifact verification over standard input/output streams via JSON-RPC 2.0.
"""

import json
from pathlib import Path
import sys
from typing import Any

from neuri.core.schemas import ModalityType, RemoteArtifact
from neuri_worker.sanitizer import NeuroHeaderSanitizer


class RemoteWorkerMCPServer:
    """Stdio JSON-RPC 2.0 tool server executing on remote compute spokes.

    Parameters
    ------------
    host_name: str
        Name of the remote host. Defaults to 'localhost'.

    Returns
    --------
        RemoteWorkerMCPServer: RemoteWorkerMCPServer instance
            Constructed remote worker server.
    """

    def __init__(self, host_name: str = "localhost") -> None:
        """Initialize remote worker server with target host name.

        Parameters
        ------------
        host_name: str
            Host identifier string. Defaults to 'localhost'.

        Returns
        --------
            None: NoneType object
                Initializes internal tools and sanitizer.
        """
        self.host_name: str = host_name
        self.sanitizer: NeuroHeaderSanitizer = NeuroHeaderSanitizer()

    def handle_request(self, request_dict: dict[str, Any]) -> dict[str, Any]:
        """Process incoming JSON-RPC 2.0 request and return response dictionary.

        Parameters
        ------------
        request_dict: dict[str, Any]
            Raw parsed JSON-RPC request dictionary.

        Returns
        --------
            dict[str, Any]: dictionary object
                JSON-RPC 2.0 response dictionary.
        """
        req_id: Any = request_dict.get("id")
        method: str = str(request_dict.get("method", ""))
        params: dict[str, Any] = request_dict.get("params", {})

        if method == "tools/list":
            tools_list: list[dict[str, Any]] = self._get_tool_definitions()
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": tools_list},
            }

        if method == "tools/call":
            tool_name: str = str(params.get("name", ""))
            args: dict[str, Any] = params.get("arguments", {})
            try:
                tool_result: dict[str, Any] = self._dispatch_tool(
                    tool_name, args
                )
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": tool_result,
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
            "error": {"code": -32601, "message": f"Method not found: '{method}'"},
        }

    def _get_tool_definitions(self) -> list[dict[str, Any]]:
        """Return MCP tool schemas supported by this remote worker.

        Parameters
        ------------
        None

        Returns
        --------
            list[dict[str, Any]]: list object
                Tool schema descriptions.
        """
        tools: list[dict[str, Any]] = [
            {
                "name": "inspect_neuro_file",
                "description": (
                    "Extract PHI-sanitized header metadata from NIfTI/EDF."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "modality": {"type": "string", "default": "T1w"},
                        "space": {"type": "string"},
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "validate_bids_directory",
                "description": (
                    "Inspect structure of BIDS dataset directory on host."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "verify_artifacts",
                "description": (
                    "Check if specified remote file paths exist on this host."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "paths": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["paths"],
                },
            },
        ]
        return tools

    def _dispatch_tool(
        self, name: str, args: dict[str, Any]
    ) -> dict[str, Any]:
        """Dispatch a tool call to its internal handler function.

        Parameters
        ------------
        name: str
            Name of tool to execute.
        args: dict[str, Any]
            Tool arguments dictionary.

        Returns
        --------
            dict[str, Any]: dictionary object
                Tool output payload.
        """
        if name == "inspect_neuro_file":
            target_path: Path = Path(str(args.get("path", "")))
            mod_str: str = str(args.get("modality", "T1w"))
            space_val: str | None = args.get("space")
            try:
                modality_enum: ModalityType = ModalityType(mod_str)
            except ValueError:
                modality_enum = ModalityType.T1W

            art: RemoteArtifact = self.sanitizer.inspect_file(
                file_path=target_path,
                modality=modality_enum,
                host=self.host_name,
                space=space_val,
            )
            return {"artifact": art.model_dump(mode="json")}

        if name == "validate_bids_directory":
            bids_dir: Path = Path(str(args.get("path", "")))
            exists: bool = bids_dir.is_dir()
            desc_file: bool = (bids_dir / "dataset_description.json").is_file()
            participants: bool = (bids_dir / "participants.tsv").is_file()
            subs: list[str] = [
                d.name for d in bids_dir.glob("sub-*") if d.is_dir()
            ]
            return {
                "valid_structure": exists and desc_file,
                "dataset_description_present": desc_file,
                "participants_tsv_present": participants,
                "subject_count": len(subs),
                "subjects": subs[:10],
            }

        if name == "verify_artifacts":
            paths_to_check: list[str] = [str(p) for p in args.get("paths", [])]
            results: dict[str, bool] = {
                p: Path(p).exists() for p in paths_to_check
            }
            all_exist: bool = all(results.values())
            return {"all_exist": all_exist, "details": results}

        raise ValueError(f"Unknown tool name: '{name}'")

    def run_stdio_loop(self) -> None:
        """Run interactive JSON-RPC stdio event loop until EOF.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Reads requests from sys.stdin and writes responses to sys.stdout.
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
    """CLI entrypoint for running remote worker stdio server.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Runs standard I/O JSON-RPC processing loop until termination.
    """
    server: RemoteWorkerMCPServer = RemoteWorkerMCPServer()
    server.run_stdio_loop()


__all__: list[str] = [
    "RemoteWorkerMCPServer",
    "main",
]
