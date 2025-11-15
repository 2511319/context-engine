from __future__ import annotations

import logging
from typing import Any, Dict, List

try:
    from neo4j import GraphDatabase  # type: ignore
except Exception:  # pragma: no cover
    GraphDatabase = None  # type: ignore

logger = logging.getLogger(__name__)


def list_modules_neo4j(uri: str, user: str, password: str, project: str) -> List[str]:
    if GraphDatabase is None:
        return []
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session() as s:
            res = s.run("MATCH (m:Module {project:$p}) RETURN m.name LIMIT 2000", p=project)
            return [r[0] for r in res]
    finally:
        driver.close()


def subgraph(uri: str, user: str, password: str, project: str, module: str, depth: int = 3) -> Dict[str, Any]:
    """
    Извлечь подграф вокруг узла Module с ограничением глубины.
    Возвращает компактный список отношений {type,target,source}.
    """
    if GraphDatabase is None:
        return {"node": module, "depth": depth, "relations": []}
    driver = GraphDatabase.driver(uri, auth=(user, password))
    rels: List[Dict[str, str]] = []
    try:
        with driver.session() as s:
            d = max(1, int(depth))
            q = (
                f"MATCH p=(m:Module)-[r*1..{d}]->(x) "
                "WHERE m.project=$p AND m.name=$n "
                "WITH r, x UNWIND r as rel "
                "RETURN DISTINCT type(rel) as t, labels(x) as lbl, x.name as name, x.path as path, x.doc_name as doc"
            )
            res = s.run(q, p=project, n=module)
            for rec in res:
                t = rec["t"]
                name = rec["name"] or rec["path"] or rec["doc"] or ""
                rels.append({"type": t, "target": str(name), "source": "neo4j"})
    except Exception as exc:  # pragma: no cover
        logger.error("neo4j subgraph failed: %s", exc)
        return {"node": module, "depth": depth, "relations": []}
    finally:
        driver.close()
    return {"node": module, "depth": depth, "relations": rels}
