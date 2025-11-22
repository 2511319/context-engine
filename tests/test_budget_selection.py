from __future__ import annotations

from pathlib import Path

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp.server import MCPServer
from core.retrieval import Candidate
from core.token_budget import count_tokens


def _server() -> MCPServer:
    root = Path(__file__).resolve().parents[1]
    return MCPServer(project_root=root)


def test_select_with_budget_respects_module_share() -> None:
    srv = _server()
    # два чанка одного модуля, бюджет = tok1+tok2, max_module_share=0.5 => второй не помещается в долю модуля
    c1 = Candidate(kind="code", project="p", path="a.py", module="mod/a", content="token " * 16, score=1.0)
    c2 = Candidate(kind="code", project="p", path="a.py", module="mod/a", content="token " * 16, score=0.9)
    tok1 = count_tokens([c1.content])
    tok2 = count_tokens([c2.content])
    total_budget = tok1 + tok2
    uri_to_module = {
        c1.uri(): "module://p/mod/a",
        c2.uri(): "module://p/mod/a",
    }
    codes, docs, snapshot = srv._select_with_budget(
        code_cands=[c1, c2],
        doc_cands=[],
        uri_to_module=uri_to_module,
        total_budget=total_budget,
        max_module_share=0.5,
    )
    # Оставляем только первый чанк (второй превышает модульный лимит)
    assert len(codes) == 1
    assert codes[0].uri() == c1.uri()
    assert snapshot["code_tokens"] == tok1
    assert snapshot["truncated_code"] == 1
    assert snapshot["max_module_share"] == 0.5


def test_select_with_budget_is_deterministic_on_equal_scores() -> None:
    srv = _server()
    c1 = Candidate(kind="code", project="p", path="a.py", module="mod/a", content="tok " * 4, score=1.0)
    c2 = Candidate(kind="code", project="p", path="b.py", module="mod/b", content="tok " * 4, score=1.0)
    uri_to_module = {c1.uri(): "module://p/mod/a", c2.uri(): "module://p/mod/b"}

    codes, docs, snapshot = srv._select_with_budget(
        code_cands=[c1, c2],
        doc_cands=[],
        uri_to_module=uri_to_module,
        total_budget=200,
    )

    assert docs == []
    assert [c.uri() for c in codes] == sorted([c1.uri(), c2.uri()])
    assert snapshot["total_tokens"] > 0
