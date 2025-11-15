import asyncio

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


class StubMCP:
    async def call_tool(self, name, arguments=None):
        await asyncio.sleep(0)
        return {"name": name, "arguments": arguments}


def test_tools_search_raw(monkeypatch):
    from api.adapters import mcp

    monkeypatch.setattr(mcp, "get_client", lambda: StubMCP())

    resp = client.post(
        "/tools/search_raw",
        json={"project": "context_engine", "query": "test", "scope": "code", "k": 2},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "search_raw"


def test_tools_get_context(monkeypatch):
    from api.adapters import mcp

    monkeypatch.setattr(mcp, "get_client", lambda: StubMCP())

    resp = client.post(
        "/tools/get_context",
        json={"project": "context_engine", "task": "demo task", "max_code_chunks": 5},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "get_context"
    assert body["arguments"]["task"] == "demo task"


def test_tools_graphify(monkeypatch):
    from api.adapters import mcp

    monkeypatch.setattr(mcp, "get_client", lambda: StubMCP())

    resp = client.post(
        "/tools/graphify",
        json={"project": "context_engine", "dry_run": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "graphify"
    assert body["arguments"]["dry_run"] is True


def test_tools_index_repo(monkeypatch):
    from api.adapters import mcp

    monkeypatch.setattr(mcp, "get_client", lambda: StubMCP())

    resp = client.post("/tools/index_repo", json={"project": "context_engine"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "index_repo"
