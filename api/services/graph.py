"""Graph-related data access."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from core.dal import GraphClient
from core.dal.repos import GraphRepo

from ..deps import get_settings

_graph_repo: GraphRepo | None = None


def _repo() -> GraphRepo:
    global _graph_repo
    if _graph_repo is None:
        settings = get_settings()
        client = GraphClient(settings.neo4j_uri_ro, settings.neo4j_user_ro, settings.neo4j_pass_ro)
        _graph_repo = GraphRepo(client)
    return _graph_repo


@dataclass
class GraphNode:
    id: str
    label: str
    props: Dict[str, Any]


@dataclass
class GraphEdge:
    source: str
    target: str
    rel_type: str


def fetch_subgraph(project: str, module: str, depth: int = 3, relations: List[str] | None = None) -> Dict[str, Any]:
    """Return nodes/edges for a module-centric subgraph."""
    result = _repo().subgraph_nodes_edges(project, module, depth, relations)
    nodes = [GraphNode(**node).__dict__ for node in result.get("nodes", [])]
    edges = [GraphEdge(**edge).__dict__ for edge in result.get("edges", [])]
    return {"nodes": nodes, "edges": edges}


def fetch_stats(project: str) -> Dict[str, Any]:
    """Return aggregate counts of nodes/edges."""
    return _repo().stats(project)
