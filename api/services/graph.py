"""Graph-related data access."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from ..adapters import neo4j


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
    nodes: Dict[str, GraphNode] = {}
    edges: List[GraphEdge] = []
    allowed = set(relations or [])
    if not allowed:
        allowed = None
    query = (
        "MATCH p=(m:Module)-[r*1..$d]->(x) "
        "WHERE m.project=$p AND m.name=$n "
        "WITH DISTINCT nodes(p) AS nds "
        "UNWIND nds AS node "
        "RETURN DISTINCT node"
    )
    rel_query = (
        "MATCH (m:Module {project:$p, name:$n})-[r*1..$d]->(x) "
        "UNWIND r as rel "
        "RETURN DISTINCT elementId(startNode(rel)) AS src_id, elementId(endNode(rel)) AS dst_id, type(rel) AS t"
    )
    with neo4j.get_driver() as driver:
        with driver.session() as session:
            for record in session.run(query, p=project, n=module, d=int(depth)):
                node = record["node"]
                name = node.get("name") or node.get("path") or node.get("doc_name") or ""
                nid = node.element_id
                label = next(iter(node.labels), "Node")
                nodes[nid] = GraphNode(
                    id=nid,
                    label=label,
                    props={
                        "name": name,
                        "path": node.get("path"),
                        "doc_name": node.get("doc_name"),
                        "project": node.get("project"),
                    },
                )
            for record in session.run(rel_query, p=project, n=module, d=int(depth)):
                rel_type = record["t"]
                if allowed and rel_type not in allowed:
                    continue
                edges.append(GraphEdge(source=record["src_id"], target=record["dst_id"], rel_type=rel_type))
    return {
        "nodes": [node.__dict__ for node in nodes.values()],
        "edges": [edge.__dict__ for edge in edges],
    }


def fetch_stats(project: str) -> Dict[str, Any]:
    """Return aggregate counts of nodes/edges."""
    stats: Dict[str, Any] = {"nodes": {}, "relations": {}}
    with neo4j.get_driver() as driver:
        with driver.session() as session:
            node_query = "MATCH (n {project:$p}) RETURN labels(n) AS lbl, count(*) AS cnt"
            for record in session.run(node_query, p=project):
                label_key = ":".join(record["lbl"])
                stats["nodes"][label_key] = record["cnt"]
            rel_query = (
                "MATCH (a {project:$p})-[r]->(b {project:$p}) "
                "RETURN type(r) AS t, count(*) AS cnt"
            )
            for record in session.run(rel_query, p=project):
                stats["relations"][record["t"]] = record["cnt"]
    return stats
