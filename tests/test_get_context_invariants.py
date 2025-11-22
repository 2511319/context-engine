from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from core.config.policy import PolicyConfig
from core.retrieval import Candidate
from mcp.server import MCPServer


def _policy(sensitive) -> PolicyConfig:
    return PolicyConfig(
        project="p",
        raw={"sensitive": sensitive},
        routing_rules=[],
        sensitive=sensitive,
        checksum="chk",
        mtime=0.0,
        ttl_seconds=30,
        source="test",
    )


def _fake_graph(*_: Any, **__: Any) -> Dict[str, Any]:
    return {"relations": []}


def _fake_hybrid(code: Tuple[Candidate, ...], docs: Tuple[Candidate, ...]):
    def _inner(*_: Any, **__: Any):
        return list(code), list(docs)

    return _inner


@pytest.fixture()
def srv(monkeypatch) -> MCPServer:
    root = Path(__file__).resolve().parents[1]
    server = MCPServer(project_root=root)
    monkeypatch.setattr("mcp.server.Health.pg_ok", staticmethod(lambda *_: True))
    monkeypatch.setattr("mcp.server.Health.neo4j_ok", staticmethod(lambda *_: True))
    monkeypatch.setattr("mcp.server.list_modules_neo4j", lambda *_, **__: [])
    monkeypatch.setattr("mcp.server.subgraph", _fake_graph)
    monkeypatch.setattr("mcp.server.get_feedback_effects", lambda *_, **__: {})
    monkeypatch.setattr("mcp.server.aggregate_by_module", lambda *_, **__: {})

    class _PgDummy:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

    monkeypatch.setattr("mcp.server.PgClient", _PgDummy)
    return server


def test_get_context_preserves_data_without_sensitive(monkeypatch, srv: MCPServer) -> None:
    code = Candidate(kind="code", project="p", path="mod/a.py", module="mod/a", content="code", score=1.0)
    doc = Candidate(kind="doc", project="p", doc_name="guide", section="intro", content="doc", score=0.4)
    monkeypatch.setattr("mcp.server.hybrid_search", _fake_hybrid((code,), (doc,)))
    monkeypatch.setattr(srv.policy_loader, "get", lambda: _policy(sensitive=[]))

    res = srv._tool_get_context({"project": "p", "task": "do api", "token_budget": 1000})

    assert res["status"] == "ok"
    assert [c["uri"] for c in res["code"]] == [code.uri()]
    assert [d["uri"] for d in res["docs"]] == [doc.uri()]
    explain = res["explain"]
    assert explain["policy_route"]["sensitive_filtered"] == []
    final_modules = {m["module_uri"] for m in explain["selection"]["final_modules"]}
    assert "module://p/mod/a" in final_modules


def test_get_context_filters_only_sensitive(monkeypatch, srv: MCPServer) -> None:
    code = Candidate(
        kind="code",
        project="p",
        path="secret/file.py",
        module="secret/file",
        content="secret",
        score=1.0,
    )
    doc = Candidate(kind="doc", project="p", doc_name="guide", section="intro", content="doc", score=0.4)
    monkeypatch.setattr("mcp.server.hybrid_search", _fake_hybrid((code,), (doc,)))
    monkeypatch.setattr(srv.policy_loader, "get", lambda: _policy(sensitive=[{"uri_pattern": "*secret*"}]))

    res = srv._tool_get_context({"project": "p", "task": "check secret", "token_budget": 1000})

    assert res["status"] == "ok"
    assert res["code"] == []  # чувствительная часть отфильтрована
    assert [d["uri"] for d in res["docs"]] == [doc.uri()]
    sens = res["explain"]["policy_route"]["sensitive_filtered"]
    assert any("secret" in s for s in sens)
    final_modules = {m["module_uri"] for m in res["explain"]["selection"]["final_modules"]}
    assert not any("secret" in m for m in final_modules)
