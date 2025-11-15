"""Adapter for interacting with the context-engine MCP server."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from asyncio.subprocess import Process
from pathlib import Path
from typing import Any, Dict, Optional


class PersistentMCPClient:
    """Persistent JSON-RPC MCP client with sequential request handling."""

    def __init__(self, server_path: Optional[Path] = None, python_exec: Optional[str] = None) -> None:
        root = Path(__file__).resolve().parents[2]
        self.server_path = server_path or (root / "mcp" / "server.py")
        self.python_exec = python_exec or sys.executable
        if not self.server_path.exists():
            raise FileNotFoundError(f"MCP server script not found at {self.server_path}")

        self._proc: Optional[Process] = None
        self._stdout: Optional[asyncio.StreamReader] = None
        self._stdin: Optional[asyncio.StreamWriter] = None
        self._stderr_task: Optional[asyncio.Task[None]] = None
        self._lock = asyncio.Lock()
        self._request_id = 0
        self.protocol_version: Optional[str] = None
        self._logger = logging.getLogger("context_engine.mcp.client")

    async def start(self) -> None:
        if self._proc and self._proc.returncode is None:
            return
        self._proc = await asyncio.create_subprocess_exec(
            self.python_exec,
            str(self.server_path),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        assert self._proc.stdout and self._proc.stdin and self._proc.stderr
        self._stdout = self._proc.stdout
        self._stdin = self._proc.stdin
        self._stderr_task = asyncio.create_task(self._pump_stderr(self._proc.stderr))
        await self._perform_handshake()

    async def stop(self) -> None:
        if self._proc and self._proc.returncode is None:
            self._proc.terminate()
            await self._proc.wait()
        if self._stderr_task:
            self._stderr_task.cancel()
        self._proc = None
        self._stdout = None
        self._stdin = None
        self._stderr_task = None

    async def ensure_running(self) -> None:
        if not self._proc or self._proc.returncode is not None:
            await self.start()

    async def list_tools(self) -> Dict[str, Any]:
        return await self._rpc("tools/list", params={})

    async def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = {"name": name, "arguments": arguments or {}}
        message = await self._rpc("tools/call", payload)
        result = message.get("result", {})
        if result.get("isError"):
            text = "; ".join(
                block.get("text", "") for block in result.get("content", []) if isinstance(block, dict)
            )
            raise RuntimeError(text or f"Tool {name} failed")
        return result.get("structuredContent") or result.get("content") or {}

    async def _perform_handshake(self) -> None:
        request_id = self._next_id()
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "clientInfo": {"name": "context-engine-ui", "version": "0.1.0"},
                "capabilities": {"tools": {}},
            },
        }
        await self._send(payload)
        response = await self._read_message()
        if response is None or response.get("id") != request_id or "result" not in response:
            raise RuntimeError("Invalid initialize response from MCP server")
        self.protocol_version = response["result"].get("protocolVersion")
        await self._send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    async def _rpc(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        await self.ensure_running()
        if not self._stdin or not self._stdout:
            raise RuntimeError("MCP process pipes unavailable")
        request_id = self._next_id()
        request = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        async with self._lock:
            await self._send(request)
            while True:
                message = await self._read_message()
                if message is None:
                    raise RuntimeError("MCP server closed the connection")
                if message.get("id") != request_id:
                    self._logger.debug("Skipping message for unexpected id: %s", message)
                    continue
                if "error" in message:
                    raise RuntimeError(str(message["error"]))
                return message

    async def _send(self, payload: Dict[str, Any]) -> None:
        if not self._stdin:
            raise RuntimeError("stdin unavailable")
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        header = f"Content-Length: {len(data)}\r\n\r\n".encode("ascii")
        self._stdin.write(header + data)
        await self._stdin.drain()

    async def _read_message(self) -> Optional[Dict[str, Any]]:
        if not self._stdout:
            return None
        while True:
            line = await self._stdout.readline()
            if not line:
                return None
            if not line.strip():
                continue
            lower = line.lower()
            if lower.startswith(b"content-length"):
                headers = await self._read_headers(line)
                length = int(headers.get("content-length", "0"))
                try:
                    data = await self._stdout.readexactly(length)
                except asyncio.IncompleteReadError:
                    return None
                return json.loads(data.decode("utf-8"))
            try:
                return json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                continue

    async def _read_headers(self, first_line: bytes) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        line = first_line
        assert self._stdout is not None
        while True:
            text = line.decode("latin-1").strip()
            if text:
                parts = text.split(":", 1)
                if len(parts) == 2:
                    headers[parts[0].lower()] = parts[1].strip()
            line = await self._stdout.readline()
            if not line or line in (b"\r\n", b"\n"):
                break
        return headers

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def _pump_stderr(self, reader: asyncio.StreamReader) -> None:
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="ignore").strip()
                if text:
                    print(f"[MCP stderr] {text}")
        except asyncio.CancelledError:
            pass


_client: Optional[PersistentMCPClient] = None


async def startup_client() -> None:
    global _client
    if _client is None:
        _client = PersistentMCPClient()
    await _client.start()


async def shutdown_client() -> None:
    global _client
    if _client is not None:
        await _client.stop()


def get_client() -> PersistentMCPClient:
    if _client is None:
        raise RuntimeError("MCP client is not initialized")
    return _client
