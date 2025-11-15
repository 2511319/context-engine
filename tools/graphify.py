from __future__ import annotations

import argparse
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

try:
    import yaml
except Exception as exc:  # pragma: no cover
    yaml = None  # type: ignore

try:
    import psycopg
except Exception as exc:  # pragma: no cover
    psycopg = None  # type: ignore

try:
    from neo4j import GraphDatabase  # type: ignore
except Exception as exc:  # pragma: no cover
    GraphDatabase = None  # type: ignore


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("context_engine.tools.graphify")


@dataclass
class Env:
    pg_dsn: str
    neo4j_uri: str
    neo4j_user: str
    neo4j_pass: str


def load_engine_cfg(path: Path) -> Dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML is required")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("engine.yml must be a mapping")
    return data


def ensure_constraints(driver) -> None:
    cql = [
        "CREATE CONSTRAINT module_unique IF NOT EXISTS FOR (m:Module) REQUIRE (m.project, m.name) IS UNIQUE",
        "CREATE CONSTRAINT contract_unique IF NOT EXISTS FOR (c:Contract) REQUIRE (c.project, c.name) IS UNIQUE",
        "CREATE CONSTRAINT docsection_unique IF NOT EXISTS FOR (d:DocSection) REQUIRE (d.project, d.doc_name, d.name) IS UNIQUE",
        "CREATE INDEX tool_name_index IF NOT EXISTS FOR (t:Tool) ON (t.name)",
    ]
    with driver.session() as s:
        for stmt in cql:
            s.run(stmt)


def project_from_cfg(cfg: Dict[str, Any]) -> str:
    return str(cfg.get("project", "context_engine"))


def project_rules(cfg: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    rules = cfg.get("routing", {}).get("rules", [])
    return rules if isinstance(rules, list) else []


def merge_module_and_docs(driver, project: str, rules: Iterable[Dict[str, Any]], dry_run: bool) -> Tuple[int, int, int]:
    mod_n = 0
    doc_n = 0
    rel_n = 0
    with driver.session() as s:
        for rule in rules:
            module = rule.get("module")
            if not module:
                continue
            if dry_run:
                mod_n += 1
            else:
                s.run("MERGE (m:Module {project:$p, name:$n, path:$n})", p=project, n=module)
                mod_n += 1
            for doc in rule.get("docs", []) or []:
                if dry_run:
                    doc_n += 1
                    rel_n += 1
                    continue
                s.run("MERGE (d:DocSection {project:$p, doc_name:$doc, name:$name})",
                      p=project, doc=doc, name=doc)
                s.run(
                    "MATCH (m:Module {project:$p, name:$n}), (d:DocSection {project:$p, doc_name:$doc, name:$name}) "
                    "MERGE (m)-[:DESCRIBED_IN]->(d)",
                    p=project, n=module, doc=doc, name=doc,
                )
                doc_n += 1
                rel_n += 1
    return mod_n, doc_n, rel_n


def project_dp_edges(conn, project: str) -> List[Tuple[str, str, str]]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT rel, src_uri, dst_uri FROM dp_edge WHERE project=%s",
            (project,),
        )
        return [(r, s, d) for (r, s, d) in cur.fetchall()]


def parse_uri(uri: str) -> Tuple[str, Dict[str, str]]:
    # file://path -> type=file, props {path}
    # doc://DocName#Section -> type=doc, props {doc_name, name}
    if uri.startswith("file://"):
        return "file", {"path": uri[len("file://"):].lstrip("/")}
    if uri.startswith("doc://"):
        rest = uri[len("doc://"):]
        if "#" in rest:
            doc_name, name = rest.split("#", 1)
        else:
            doc_name, name = rest, rest
        return "doc", {"doc_name": doc_name, "name": name}
    return "unknown", {"raw": uri}


def merge_edges(driver, project: str, edges: Iterable[Tuple[str, str, str]], dry_run: bool) -> int:
    count = 0
    with driver.session() as s:
        for rel, src, dst in edges:
            src_t, src_p = parse_uri(src)
            dst_t, dst_p = parse_uri(dst)
            if src_t == "file":
                if not dry_run:
                    s.run("MERGE (m:Module {project:$p, name:$n, path:$n})", p=project, n=src_p["path"])
                src_match = "(m:Module {project:$p, name:$src})"
            elif src_t == "doc":
                if not dry_run:
                    s.run("MERGE (d:DocSection {project:$p, doc_name:$doc, name:$name})", p=project, doc=src_p["doc_name"], name=src_p["name"])
                src_match = "(d:DocSection {project:$p, doc_name:$doc_src, name:$name_src})"
            else:
                continue

            if dst_t == "file":
                if not dry_run:
                    s.run("MERGE (m2:Module {project:$p, name:$n, path:$n})", p=project, n=dst_p["path"])
                dst_match = "(m2:Module {project:$p, name:$dst})"
            elif dst_t == "doc":
                if not dry_run:
                    s.run("MERGE (d2:DocSection {project:$p, doc_name:$doc, name:$name})", p=project, doc=dst_p["doc_name"], name=dst_p["name"])
                dst_match = "(d2:DocSection {project:$p, doc_name:$doc_dst, name:$name_dst})"
            else:
                continue

            if dry_run:
                count += 1
                continue

            if rel not in {"DESCRIBED_IN", "IMPLEMENTS", "REFERENCES"}:
                continue

            s.run(
                f"MATCH {src_match}, {dst_match} MERGE "+
                (" (m)-[:DESCRIBED_IN]->(d2)" if rel == "DESCRIBED_IN" else
                 " (m)-[:IMPLEMENTS]->(m2)" if rel == "IMPLEMENTS" else
                 " (m)-[:REFERENCES]->(m2)"),
                p=project,
                src=src_p.get("path"),
                dst=dst_p.get("path"),
                doc_src=src_p.get("doc_name"),
                name_src=src_p.get("name"),
                doc_dst=dst_p.get("doc_name"),
                name_dst=dst_p.get("name"),
            )
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Project stable graph projection into Neo4j")
    parser.add_argument("--project", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    cfg = load_engine_cfg(repo / "config" / "engine.yml")
    project = args.project or project_from_cfg(cfg)

    if GraphDatabase is None:
        raise RuntimeError("neo4j driver is required")
    if psycopg is None:
        raise RuntimeError("psycopg (psycopg3) is required")

    env = Env(
        pg_dsn=os.getenv("PG_DSN", ""),
        neo4j_uri=os.getenv("NEO4J_URI", ""),
        neo4j_user=os.getenv("NEO4J_USER", ""),
        neo4j_pass=os.getenv("NEO4J_PASS", ""),
    )

    if not env.pg_dsn:
        raise RuntimeError("PG_DSN is not set")
    if not (env.neo4j_uri and env.neo4j_user and env.neo4j_pass):
        raise RuntimeError("NEO4J credentials are not set")

    driver = GraphDatabase.driver(env.neo4j_uri, auth=(env.neo4j_user, env.neo4j_pass))
    ensure_constraints(driver)

    with psycopg.connect(env.pg_dsn, autocommit=True) as conn:
        rules = list(project_rules(cfg))
        mod_n, doc_n, rel_n = merge_module_and_docs(driver, project, rules, args.dry_run)
        edges = project_dp_edges(conn, project)
        edge_n = merge_edges(driver, project, edges, args.dry_run)

    logger.info("graphify: modules=%d docs=%d described_in=%d dp_edges=%d (dry_run=%s)", mod_n, doc_n, rel_n, edge_n, args.dry_run)


if __name__ == "__main__":
    main()
