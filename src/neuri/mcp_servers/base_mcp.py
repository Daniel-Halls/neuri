"""Base Model Context Protocol (MCP) Stdio JSON-RPC 2.0 Server.

Provides the canonical lifecycle contract for MCP stdio servers compliant with
the MCP 2024-11-05 specification.
"""

from abc import ABC, abstractmethod
import json
import sys
from typing import Any


class BaseMCPStdioServer(ABC):
    """Abstract base class for Model Context Protocol (MCP) stdio servers.

    Parameters
    ------------
    None

    Returns
    --------
        BaseMCPStdioServer: BaseMCPStdioServer instance
            Constructed base server instance.
    """

    PROTOCOL_VERSION: str = "2024-11-05"

    def __init__(self) -> None:
        """Initialize base MCP stdio server.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Initializes internal base state.
        """
        super().__init__()

    @property
    @abstractmethod
    def server_name(self) -> str:
        """Return the unique name of this MCP server.

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                Server identifier string.
        """
        pass

    @property
    def server_version(self) -> str:
        """Return the version string of this MCP server.

        Parameters
        ------------
        None

        Returns
        --------
            str: string object
                Semantic version string. Defaults to '0.1.0'.
        """
        version_str: str = "0.1.0"
        return version_str

    @abstractmethod
    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Return JSON-schema tool definitions exposed by this MCP server.

        Parameters
        ------------
        None

        Returns
        --------
            list[dict[str, Any]]: list object
                Tool definition dictionaries matching MCP tools/list format.
        """
        pass

    @abstractmethod
    def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> Any:
        """Execute a declared MCP tool with provided input arguments.

        Parameters
        ------------
        tool_name: str
            Name of the tool to invoke.
        arguments: dict[str, Any]
            Arguments dictionary for tool execution.

        Returns
        --------
            Any: object
                Tool execution output (dictionary, string, or primitive).
        """
        pass

    def handle_request(
        self, request_dict: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Process incoming JSON-RPC 2.0 request and formulate response.

        Handles initialize handshake, notifications, ping, tools/list, and
        tools/call in accordance with the MCP specification.

        Parameters
        ------------
        request_dict: dict[str, Any]
            Raw JSON-RPC request dictionary.

        Returns
        --------
            dict[str, Any] | None: dictionary object or None
                Response dictionary or None for notifications.
        """
        req_id: Any = request_dict.get("id")
        method: str = str(request_dict.get("method", ""))
        params: dict[str, Any] = request_dict.get("params", {})

        if method in ("notifications/initialized", "initialized"):
            return None

        if method == "initialize":
            init_resp: dict[str, Any] = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": self.PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": self.server_name,
                        "version": self.server_version,
                    },
                },
            }
            return init_resp

        if method == "ping":
            ping_resp: dict[str, Any] = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {},
            }
            return ping_resp

        if method == "tools/list":
            list_resp: dict[str, Any] = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": self.get_tool_definitions()},
            }
            return list_resp

        if method == "tools/call":
            tool_name: str = str(params.get("name", ""))
            tool_args: dict[str, Any] = params.get("arguments", {})
            try:
                raw_out: Any = self.call_tool(tool_name, tool_args)
                text_content: str = (
                    json.dumps(raw_out, indent=2)
                    if isinstance(raw_out, (dict, list))
                    else str(raw_out)
                )
                call_resp: dict[str, Any] = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": text_content}
                        ]
                    },
                }
                return call_resp
            except Exception as exc:
                err_call_resp: dict[str, Any] = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": f"Error: {exc}"}
                        ],
                        "isError": True,
                    },
                }
                return err_call_resp

        err_resp: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method '{method}' not found",
            },
        }
        return err_resp

    def run_stdio_loop(self) -> None:
        """Run blocking stdio read loop for JSON-RPC 2.0 communication.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Processes stdin line by line until EOF.
        """
        for line in sys.stdin:
            stripped: str = line.strip()
            if not stripped:
                continue
            try:
                req: dict[str, Any] = json.loads(stripped)
                resp: dict[str, Any] | None = self.handle_request(req)
                if resp is not None:
                    sys.stdout.write(json.dumps(resp) + "\n")
                    sys.stdout.flush()
            except Exception as exc:
                err_payload: dict[str, Any] = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {exc}"},
                }
                sys.stdout.write(json.dumps(err_payload) + "\n")
                sys.stdout.flush()


__all__: list[str] = [
    "BaseMCPStdioServer",
]
