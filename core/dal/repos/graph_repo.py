from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..neo4j import GraphClient

logger = logging.getLogger(__name__)


class GraphRepo:
    """Graph operations backed by Neo4j."""

    def __init__(self, graph: GraphClient) -> None:
        self.graph = graph

    def list_modules(self, project: str, limit: int = 2000) -> List[str]:
        cypher = "MATCH (m:Module {project:$p}) RETURN m.name AS name LIMIT $limit"
        try:
            return [r["name"] for r in self.graph.run(cypher, {"p": project, "limit": int(limit)}) if r.get("name")]
        except Exception as exc:  # pragma: no cover
            logger.error("list_modules failed: %s", exc)
            return []

    def subgraph(self, project: str, module: str, depth: int = 3) -> Dict[str, Any]:
        """Extract compact relations around a module node."""
        relations: List[Dict[str, str]] = []
        try:
            d = max(1, int(depth))
            cypher = (
                f"MATCH p=(m:Module)-[r*1..{d}]->(x) "
                "WHERE m.project=$p AND m.name=$n "
                "WITH r, x UNWIND r as rel "
                "RETURN DISTINCT type(rel) as t, labels(x) as lbl, x.name as name, x.path as path, x.doc_name as doc"
            )
            for rec in self.graph.run(cypher, {"p": project, "n": module}):
                target_name = rec.get("name") or rec.get("path") or rec.get("doc") or ""
                relations.append({"type": rec.get("t"), "target": str(target_name), "source": "neo4j"})
        except Exception as exc:  # pragma: no cover
            logger.error("subgraph failed: %s", exc)
            return {"node": module, "depth": depth, "relations": []}
        return {"node": module, "depth": depth, "relations": relations}

    def stats(self, project: str) -> Dict[str, Any]:
        """Return aggregate counts of nodes/edges for a project."""
        stats: Dict[str, Any] = {"nodes": {}, "relations": {}}
        try:
            node_query = "MATCH (n {project:$p}) RETURN labels(n) AS lbl, count(*) AS cnt"
            for record in self.graph.run(node_query, {"p": project}):
                label_key = ":".join(record.get("lbl", []))
                stats["nodes"][label_key] = record.get("cnt", 0)
            rel_query = "MATCH (a {project:$p})-[r]->(b {project:$p}) RETURN type(r) AS t, count(*) AS cnt"
            for record in self.graph.run(rel_query, {"p": project}):
                stats["relations"][record.get("t")] = record.get("cnt", 0)
        except Exception as exc:  # pragma: no cover
            logger.error("graph stats failed: %s", exc)
        return stats

    def subgraph_nodes_edges(self, project: str, module: str, depth: int = 3, relations: List[str] | None = None) -> Dict[str, Any]:
        """Return nodes/edges representation for a module-centric subgraph."""
        nodes: Dict[str, Dict[str, Any]] = {}
        edges: List[Dict[str, Any]] = []
        allowed = set(relations or [])
        allowed_set = allowed if allowed else None
        try:
            node_query = (
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
            for record in self.graph.run(node_query, {"p": project, "n": module, "d": int(depth)}):
                node = record.get("node", {})
                name = node.get("name") or node.get("path") or node.get("doc_name") or ""
                nid = node.element_id  # type: ignore[attr-defined]
                label = next(iter(node.labels), "Node")  # type: ignore[attr-defined]
                nodes[nid] = {
                    "id": nid,
                    "label": label,
                    "props": {
                        "name": name,
                        "path": node.get("path"),
                        "doc_name": node.get("doc_name"),
                        "project": node.get("project"),
                    },
                }
            for record in self.graph.run(rel_query, {"p": project, "n": module, "d": int(depth)}):
                rel_type = record.get("t")
                if allowed_set and rel_type not in allowed_set:
                    continue
                edges.append({"source": record.get("src_id"), "target": record.get("dst_id"), "rel_type": rel_type})
        except Exception as exc:  # pragma: no cover
            logger.error("subgraph_nodes_edges failed: %s", exc)
        return {"nodes": list(nodes.values()), "edges": edges}
