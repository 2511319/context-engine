from __future__ import annotations

import logging
from typing import Any, Dict, List

from core.dal.neo4j import GraphClient
from core.dal.repos.graph_repo import GraphRepo

logger = logging.getLogger(__name__)


def _repo(uri: str, user: str, password: str) -> GraphRepo | None:
    try:
        client = GraphClient(uri, user, password)
        return GraphRepo(client)
    except Exception:  # pragma: no cover
        return None


def list_modules_neo4j(uri: str, user: str, password: str, project: str) -> List[str]:
    repo = _repo(uri, user, password)
    if repo is None:
        return []
    return repo.list_modules(project)


def subgraph(uri: str, user: str, password: str, project: str, module: str, depth: int = 3) -> Dict[str, Any]:
    """
    Извлечь подграф вокруг узла Module с ограничением глубины.
    Возвращает компактный список отношений {type,target,source}.
    """
    repo = _repo(uri, user, password)
    if repo is None:
        return {"node": module, "depth": depth, "relations": []}
    return repo.subgraph(project, module, depth)
