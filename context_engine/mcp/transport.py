from __future__ import annotations

import json
import re
import sys
from io import BufferedReader, BufferedWriter
from typing import Any, Dict, Optional

_HEADER_RE = re.compile(r"^(?P<name>[^:]+):\s*(?P<value>.+)$")


class StdioJSONRPCTransport:
    """
    Basic JSON-RPC transport over stdio using the same framing as LSP/MCP
    (Content-Length headers + CRLF separator). Falls back to newline-delimited
    JSON for compatibility with older prototypes.
    """

    def __init__(
        self,
        reader: Optional[BufferedReader] = None,
        writer: Optional[BufferedWriter] = None,
        encoding: str = "utf-8",
    ) -> None:
        self.reader = reader or sys.stdin.buffer
        self.writer = writer or sys.stdout.buffer
        self.encoding = encoding

    def read_message(self) -> Optional[Dict[str, Any]]:
        """Read the next JSON-RPC message. Returns None on EOF."""
        while True:
            first_line = self.reader.readline()
            if not first_line:
                return None
            if not first_line.strip():
                continue

            lower = first_line.lower()
            if lower.startswith(b"content-length"):
                headers = self._read_headers(first_line)
                length = int(headers.get("content-length", "0"))
                body = self.reader.read(length)
                if not body:
                    return None
                return json.loads(body.decode(self.encoding))

            # Fallback for newline-delimited JSON prototypes
            try:
                return json.loads(first_line.decode(self.encoding))
            except json.JSONDecodeError:
                # Attempt to accumulate until a blank line
                buffer = bytearray(first_line)
                while True:
                    chunk = self.reader.readline()
                    if not chunk or not chunk.strip():
                        break
                    buffer.extend(chunk)
                try:
                    return json.loads(buffer.decode(self.encoding))
                except json.JSONDecodeError as exc:
                    raise RuntimeError(f"Failed to parse JSON-RPC message: {exc}") from exc

    def write_message(self, payload: Dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode(self.encoding)
        header = f"Content-Length: {len(data)}\r\n\r\n".encode("ascii")
        self.writer.write(header)
        self.writer.write(data)
        self.writer.flush()

    def _read_headers(self, first_line: bytes) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        line = first_line
        while True:
            decoded = line.decode("latin-1").strip()
            if decoded:
                match = _HEADER_RE.match(decoded)
                if match:
                    headers[match.group("name").lower()] = match.group("value")
            line = self.reader.readline()
            if not line or line in (b"\r\n", b"\n"):
                break
        return headers
