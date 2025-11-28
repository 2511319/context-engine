from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.adapters.mcp import PersistentMCPClient


async def call_safe(fn, *args, **kwargs) -> Dict[str, Any]:
    try:
        return await fn(*args, **kwargs)
    except Exception as exc:
        return {"isError": True, "error": str(exc)}


async def smoke_project(client: PersistentMCPClient, project: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {"project": project, "list_tools": None, "search_raw": None, "get_context": None}
    tools = await call_safe(client.list_tools)
    result["list_tools"] = tools

    search_args = {"project": project, "query": "health", "scope": "both", "k": 2}
    result["search_raw"] = await call_safe(client.call_tool, "search_raw", search_args)

    ctx_args = {
        "project": project,
        "task": f"smoke test for {project}",
        "max_code_chunks": 2,
        "max_doc_chunks": 2,
        "graph_depth": 2,
    }
    result["get_context"] = await call_safe(client.call_tool, "get_context", ctx_args)
    return result


def summarize(res: Dict[str, Any]) -> str:
    def status(entry: Any) -> str:
        if isinstance(entry, dict) and entry.get("isError"):
            return f"error: {entry.get('error')}"
        return "ok"

    return (
        f"{res['project']}: "
        f"tools={status(res['list_tools'])}, "
        f"search={status(res['search_raw'])}, "
        f"get_context={status(res['get_context'])}"
    )


async def main(projects: List[str]) -> None:
    client = PersistentMCPClient()
    await client.start()
    try:
        results = [await smoke_project(client, p) for p in projects]
    finally:
        await client.stop()
    for res in results:
        print(summarize(res))
        if isinstance(res.get("get_context"), dict) and res["get_context"].get("plan_id"):
            print(f"  plan_id: {res['get_context']['plan_id']}")


if __name__ == "__main__":
    projects = sys.argv[1:] or ["context_engine", "mimic_codex"]
    asyncio.run(main(projects))
