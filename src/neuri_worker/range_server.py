"""Byte-range HTTP daemon for remote neuroimaging streaming in Neuri.

Provides a lightweight, zero-token daemon running on remote compute spokes
bound to 127.0.0.1 that serves NIfTI, GIfTI, and tractography files with HTTP
Range (206 Partial Content) support over SSH port forwarding.
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
import os
from pathlib import Path
import re
import socketserver
import sys
import threading
from typing import Any


class ByteRangeHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler supporting HTTP Range requests and directory whitelisting.

    Parameters
    ------------
    request: Any
        Underlying socket connection request.
    client_address: tuple[str, int]
        Tuple of client IP address and port.
    server: HTTPServer
        Parent HTTP server instance.

    Returns
    --------
        ByteRangeHTTPHandler: ByteRangeHTTPHandler instance
            Constructed handler instance.
    """

    server_version: str = "NeuriRangeServer/0.1"

    def parse_range_header(
        self, range_header: str, file_size: int
    ) -> tuple[int, int] | None:
        """Parse HTTP Range header into 0-indexed byte bounds.

        Parameters
        ------------
        range_header: str
            Raw HTTP Range header string (e.g. 'bytes=0-1023').
        file_size: int
            Total size of the target file in bytes.

        Returns
        --------
            tuple[int, int] | None: tuple or None
                Tuple of (start_byte, end_byte) inclusive, or None if invalid.
        """
        match = re.match(r"^bytes=(\d*)-(\d*)$", range_header.strip())
        if not match:
            return None

        start_str, end_str = match.groups()
        if not start_str and not end_str:
            return None

        if not start_str:
            suffix_len: int = int(end_str)
            start_byte: int = max(0, file_size - suffix_len)
            end_byte: int = file_size - 1
            return (start_byte, end_byte)

        start_byte = int(start_str)
        if start_byte >= file_size:
            return None

        if not end_str:
            end_byte = file_size - 1
        else:
            end_byte = min(int(end_str), file_size - 1)

        if start_byte > end_byte:
            return None

        return (start_byte, end_byte)

    def guess_content_type(self, file_path: Path) -> str:
        """Determine MIME type based on neuroimaging file suffix.

        Parameters
        ------------
        file_path: Path
            Path to the target file.

        Returns
        --------
            str: string object
                MIME type string.
        """
        name_lower: str = file_path.name.lower()
        if name_lower.endswith(".nii.gz"):
            return "application/gzip"
        elif name_lower.endswith(".nii"):
            return "application/octet-stream"
        elif name_lower.endswith(".tck") or name_lower.endswith(".trk"):
            return "application/octet-stream"
        elif name_lower.endswith(".gii"):
            return "application/octet-stream"
        elif name_lower.endswith(".json"):
            return "application/json"
        elif name_lower.endswith(".png"):
            return "image/png"
        elif name_lower.endswith(".svg"):
            return "image/svg+xml"
        return "application/octet-stream"

    def is_path_permitted(self, file_path: Path) -> bool:
        """Verify resolved path resides within configured allowed roots.

        Parameters
        ------------
        file_path: Path
            Resolved absolute path to verify.

        Returns
        --------
            bool: boolean object
                True if path is within an allowed root directory.
        """
        allowed: list[Path] = getattr(self.server, "allowed_roots", [])
        if not allowed:
            return True
        try:
            resolved_target: Path = file_path.resolve()
            for root in allowed:
                resolved_root: Path = root.resolve()
                if (
                    resolved_target == resolved_root
                    or resolved_root in resolved_target.parents
                ):
                    return True
        except Exception:
            return False
        return False

    def handle_head(self) -> None:
        """Handle HTTP HEAD requests by returning headers without body.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Sends HTTP response headers.
        """
        self._serve_file(send_body=False)

    def handle_get(self) -> None:
        """Handle HTTP GET requests with Range support.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Sends HTTP response headers and body content.
        """
        self._serve_file(send_body=True)

    do_HEAD = handle_head
    do_GET = handle_get

    def _serve_file(self, send_body: bool = True) -> None:
        """Serve target file with support for partial byte ranges.

        Parameters
        ------------
        send_body: bool
            Whether to write file bytes to response stream. Defaults to True.

        Returns
        --------
            None: NoneType object
                Writes HTTP response.
        """
        raw_path: str = self.path.split("?")[0]
        file_path: Path = Path(raw_path)

        if not self.is_path_permitted(file_path):
            self.send_error(403, "Access to path forbidden")
            return

        if not file_path.is_file():
            self.send_error(404, "File not found")
            return

        try:
            total_size: int = file_path.stat().st_size
        except OSError:
            self.send_error(500, "Unable to stat file")
            return

        content_type: str = self.guess_content_type(file_path)
        range_header: str | None = self.headers.get("Range")

        if range_header:
            parsed_range = self.parse_range_header(range_header, total_size)
            if parsed_range is None:
                self.send_response(416, "Range Not Satisfiable")
                self.send_header(
                    "Content-Range", f"bytes */{total_size}"
                )
                self.end_headers()
                return

            start_byte, end_byte = parsed_range
            chunk_length: int = end_byte - start_byte + 1

            self.send_response(206, "Partial Content")
            self.send_header("Content-Type", content_type)
            self.send_header(
                "Content-Range",
                f"bytes {start_byte}-{end_byte}/{total_size}",
            )
            self.send_header("Content-Length", str(chunk_length))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()

            if send_body:
                try:
                    with file_path.open("rb") as f:
                        f.seek(start_byte)
                        bytes_left: int = chunk_length
                        while bytes_left > 0:
                            read_len: int = min(65536, bytes_left)
                            buf: bytes = f.read(read_len)
                            if not buf:
                                break
                            self.wfile.write(buf)
                            bytes_left -= len(buf)
                except (ConnectionError, OSError):
                    pass
        else:
            self.send_response(200, "OK")
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(total_size))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()

            if send_body:
                try:
                    with file_path.open("rb") as f:
                        while True:
                            buf = f.read(65536)
                            if not buf:
                                break
                            self.wfile.write(buf)
                except (ConnectionError, OSError):
                    pass

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress standard logging to stderr in daemon mode.

        Parameters
        ------------
        format: str
            Log format string.
        *args: Any
            Log arguments.

        Returns
        --------
            None: NoneType object
                No-op suppression.
        """
        pass


class ByteRangeHTTPServer:
    """Threaded HTTP daemon providing byte-range streaming for neuroimaging.

    Parameters
    ------------
    host: str
        Binding host address. Defaults to '127.0.0.1'.
    port: int
        Binding port number. Defaults to 8422.
    allowed_roots: list[Path] | None
        List of directory paths allowed for serving. Defaults to None.

    Returns
    --------
        ByteRangeHTTPServer: ByteRangeHTTPServer instance
            Constructed range server controller.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8422,
        allowed_roots: list[Path] | None = None,
    ) -> None:
        """Initialize daemon configuration.

        Parameters
        ------------
        host: str
            Binding host address. Defaults to '127.0.0.1'.
        port: int
            Binding port number. Defaults to 8422.
        allowed_roots: list[Path] | None
            Allowed root paths. Defaults to None.

        Returns
        --------
            None: NoneType object
                Initializes server state.
        """
        self._host: str = host
        self._port: int = port
        self._allowed_roots: list[Path] = (
            allowed_roots if allowed_roots is not None else []
        )
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._is_running: bool = False

    def start(self) -> None:
        """Start the byte range HTTP server in a background thread.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Spawns daemon thread and begins serving.
        """
        if self._is_running:
            return

        server = HTTPServer((self._host, self._port), ByteRangeHTTPHandler)
        setattr(server, "allowed_roots", self._allowed_roots)
        self._server = server
        self._port = server.server_address[1]
        self._is_running = True

        thread = threading.Thread(
            target=self._server.serve_forever, daemon=True
        )
        self._thread = thread
        thread.start()

    def stop(self) -> None:
        """Stop the byte range HTTP server and join thread.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Shuts down server instance.
        """
        if not self._is_running or self._server is None:
            return

        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._is_running = False

    def get_server_port(self) -> int:
        """Retrieve the actual active server port.

        Parameters
        ------------
        None

        Returns
        --------
            int: integer object
                Port number on which server is listening.
        """
        return self._port

    def is_running(self) -> bool:
        """Check whether the server daemon is active.

        Parameters
        ------------
        None

        Returns
        --------
            bool: boolean object
                True if server is currently serving requests.
        """
        return self._is_running

    def run_forever(self) -> None:
        """Run the server synchronously on the calling thread.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Serves requests indefinitely until interrupted.
        """
        server = HTTPServer((self._host, self._port), ByteRangeHTTPHandler)
        setattr(server, "allowed_roots", self._allowed_roots)
        self._server = server
        self._port = server.server_address[1]
        self._is_running = True
        try:
            server.serve_forever()
        finally:
            server.server_close()
            self._is_running = False


def main() -> None:
    """CLI entrypoint for running neuri-vis-daemon on remote nodes.

    Parameters
    ------------
    None

    Returns
    --------
        None: NoneType object
            Executes range server process.
    """
    port_val: int = 8422
    if len(sys.argv) > 1:
        try:
            port_val = int(sys.argv[1])
        except ValueError:
            pass

    server: ByteRangeHTTPServer = ByteRangeHTTPServer(
        host="127.0.0.1", port=port_val
    )
    server.run_forever()


if __name__ == "__main__":
    main()
