from __future__ import annotations

import json
import subprocess
import sys
import time

SERVER_CMD = [sys.executable, "mcp/server.py"]

proc = subprocess.Popen(
    SERVER_CMD,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)
try:
    message = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "clientInfo": {"name": "test", "version": "0"},
            "capabilities": {"tools": {}},
        },
    }
    data = json.dumps(message, ensure_ascii=False).encode("utf-8")
    payload = f"Content-Length: {len(data)}\r\n\r\n".encode("ascii") + data
    assert proc.stdin is not None
    proc.stdin.write(payload)
    proc.stdin.flush()
    time.sleep(0.5)
    assert proc.stdout is not None
    header = proc.stdout.readline().decode("utf-8", errors="ignore")
    body = b""
    if header.lower().startswith("content-length"):
        length = int(header.split(":", 1)[1].strip())
        proc.stdout.readline()  # blank line
        body = proc.stdout.read(length)
    else:
        body = header.encode("utf-8")
    print("HEADER:", header.strip())
    print("BODY:", body.decode("utf-8", errors="ignore"))
finally:
    proc.kill()
    stderr = proc.stderr.read().decode("utf-8", errors="ignore") if proc.stderr else ""
    print("STDERR:", stderr)
