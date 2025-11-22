from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.policy.routing import RoutingEffects
from core.retrieval import Candidate
from mcp.server import MCPServer


def _server() -> MCPServer:
    root = Path(__file__).resolve().parents[1]
    return MCPServer(project_root=root)


def test_policy_keeps_data_without_sensitive_rules() -> None:
    srv = _server()
    code = Candidate(kind="code", project="p", path="mod/a.py", module="mod/a", content="c", score=1.0)
    doc = Candidate(kind="doc", project="p", doc_name="guide", section="intro", content="d", score=0.5)
    modules = srv._aggregate_modules("p", [code], [doc])
    routing = RoutingEffects(
        module_boosts={"module://p/mod/a": 0.7},
        boost_tags={"scope:api"},
        code_weight=0.5,
        doc_weight=1.2,
        max_tokens_share=0.6,
    )

    filtered: list[str] = []
    code_adj, doc_adj, modules_adj = srv._apply_policy(
        project="p",
        code_cands=[code],
        doc_cands=[doc],
        modules=modules,
        routing_effects=routing,
        fb_by_uri={},
        fb_by_module={},
        sensitive_rules=[],
        sensitive_filtered=filtered,
    )

    assert {c.uri() for c in code_adj} == {code.uri()}
    assert {c.uri() for c in doc_adj} == {doc.uri()}
    assert set(modules_adj.keys()) == set(modules.keys())
    assert not filtered
    assert modules_adj["module://p/mod/a"]["final_score"] > modules_adj["module://p/mod/a"]["base_score"]


def test_sensitive_rules_remove_matching_chunks_and_modules() -> None:
    srv = _server()
    code = Candidate(kind="code", project="p", path="secret/file.py", module="secret/file", content="c", score=1.0)
    doc = Candidate(kind="doc", project="p", doc_name="public", section="intro", content="d", score=0.4)
    modules = srv._aggregate_modules("p", [code], [doc])

    filtered: list[str] = []
    code_adj, doc_adj, modules_adj = srv._apply_policy(
        project="p",
        code_cands=[code],
        doc_cands=[doc],
        modules=modules,
        routing_effects=None,
        fb_by_uri={},
        fb_by_module={},
        sensitive_rules=[{"uri_pattern": "*secret*"}],
        sensitive_filtered=filtered,
    )

    assert not code_adj
    assert {c.uri() for c in doc_adj} == {doc.uri()}
    assert "module://p/secret/file" not in modules_adj
    assert any("secret" in entry for entry in filtered)
