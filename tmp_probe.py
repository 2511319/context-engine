from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from api.adapters.mcp import PersistentMCPClient


def load_env() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, _, value = stripped.partition("=")
            os.environ[key.strip()] = value.strip()


async def call_tool(client: PersistentMCPClient, name: str, args: dict, timeout: float) -> dict | None:
    try:
        return await asyncio.wait_for(client.call_tool(name, args), timeout=timeout)
    except Exception as exc:
        print(f"{name} failed: {exc}")
        return None


async def main() -> None:
    load_env()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    client = PersistentMCPClient()
    await client.start()
    try:
        tools_msg = await client.list_tools()
        tools = [t.get("name") for t in tools_msg.get("result", {}).get("tools", [])]
        print("TOOLS:", tools)

        search_args = {"project": "mimic_codex", "query": "memory", "scope": "both", "k": 3}
        search = await call_tool(client, "search_raw", search_args, timeout=90)
        if search:
            items = search.get("items", [])
            print(f"SEARCH_RAW items={len(items)}")
            for it in items[:3]:
                print(f"- {it.get('path_or_doc','')}: score={it.get('score')}")

        ctx_args = {
            "project": "mimic_codex",
            "task": "как устроена память в mimic_codex",
            "max_code_chunks": 3,
            "max_doc_chunks": 2,
            "graph_depth": 2,
        }
        ctx = await call_tool(client, "get_context", ctx_args, timeout=120)
        if ctx:
            code = ctx.get("code") or []
            docs = ctx.get("docs") or []
            print(f"GET_CONTEXT status={ctx.get('status')} plan_id={ctx.get('plan_id')} code={len(code)} docs={len(docs)}")
    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
