from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.dal import GraphClient, PgClient
from core.dal.repos import IngestRepo
from core.uri import doc_uri, docsection_uri, file_uri, module_uri, symbol_uri

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("context_engine.tools.graphify")


def _load_env(env_path: Path) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        os.environ[key.strip()] = value.strip()


@dataclass
class Env:
    pg_dsn: str
    neo4j_uri: str
    neo4j_user: str
    neo4j_pass: str


def ensure_constraints(graph: GraphClient) -> None:
    cql = [
        "CREATE CONSTRAINT file_unique IF NOT EXISTS FOR (f:File) REQUIRE (f.project, f.uri) IS UNIQUE",
        "CREATE CONSTRAINT module_unique IF NOT EXISTS FOR (m:Module) REQUIRE (m.project, m.uri) IS UNIQUE",
        "CREATE CONSTRAINT symbol_unique IF NOT EXISTS FOR (s:Symbol) REQUIRE (s.project, s.uri) IS UNIQUE",
        "CREATE CONSTRAINT doc_unique IF NOT EXISTS FOR (d:Doc) REQUIRE (d.project, d.uri) IS UNIQUE",
        "CREATE CONSTRAINT docsection_unique IF NOT EXISTS FOR (ds:DocSection) REQUIRE (ds.project, ds.uri) IS UNIQUE",
    ]
    with graph.session() as s:
        for stmt in cql:
            s.run(stmt)


def normalize_code_row(project: str, row: Sequence[Any]) -> Tuple[str, str, str]:
    uri, path, module = row
    path = str(path)
    uri = uri or file_uri(project, path)
    module_name = module or path
    return uri, path, module_name


def normalize_doc_row(project: str, row: Sequence[Any]) -> Tuple[str, str, str, str]:
    uri, doc_name, section = row
    doc_name = doc_name or "doc"
    section = section or "sec-1-1"
    section_uri = uri or docsection_uri(project, doc_name, section)
    base_uri = doc_uri(project, doc_name)
    return base_uri, section_uri, doc_name, section


def build_symbol_uri(project: str, name: str, module: str | None, path: str | None, uri: str | None) -> str:
    if uri:
        return uri
    mod = module or (path or "").replace(".py", "")
    return symbol_uri(project, mod, name)


def dry_run_summary(project: str, code_rows, doc_rows, symbols, edges) -> Dict[str, Any]:
    return {
        "project": project,
        "nodes": {
            "files": len(code_rows),
            "doc_sections": len(doc_rows),
            "symbols": len(symbols),
        },
        "edges": len(edges),
    }


def apply_graph(graph: GraphClient, project: str, code_rows, doc_rows, symbols, edges) -> Dict[str, int]:
    created = {"nodes": 0, "edges": 0}
    with graph.session() as s:
        for row in code_rows:
            uri, path, module_name = normalize_code_row(project, row)
            mod_uri = module_uri(project, module_name)
            s.run("MERGE (f:File {project:$p, uri:$u}) SET f.path=$path", p=project, u=uri, path=path)
            s.run("MERGE (m:Module {project:$p, uri:$u}) SET m.name=$name", p=project, u=mod_uri, name=module_name)
            s.run(
                "MATCH (f:File {project:$p, uri:$fu}), (m:Module {project:$p, uri:$mu}) "
                "MERGE (f)-[r:PART_OF_MODULE {project:$p}]->(m)",
                p=project,
                fu=uri,
                mu=mod_uri,
            )
            created["nodes"] += 1

        for row in doc_rows:
            base_uri, section_uri, doc_name, section = normalize_doc_row(project, row)
            s.run("MERGE (d:Doc {project:$p, uri:$u}) SET d.name=$name", p=project, u=base_uri, name=doc_name)
            s.run(
                "MERGE (ds:DocSection {project:$p, uri:$u}) SET ds.doc_name=$doc, ds.section_id=$sec",
                p=project,
                u=section_uri,
                doc=doc_name,
                sec=section,
            )
            s.run(
                "MATCH (d:Doc {project:$p, uri:$du}), (ds:DocSection {project:$p, uri:$su}) "
                "MERGE (d)-[r:HAS_SECTION {project:$p}]->(ds)",
                p=project,
                du=base_uri,
                su=section_uri,
            )
            created["nodes"] += 1

        for uri, name, module, path, kind in symbols:
            sym_uri = build_symbol_uri(project, name, module, path, uri)
            s.run(
                "MERGE (sym:Symbol {project:$p, uri:$u}) "
                "SET sym.name=$name, sym.module=$module, sym.path=$path, sym.kind=$kind",
                p=project,
                u=sym_uri,
                name=name,
                module=module,
                path=path,
                kind=kind,
            )
            created["nodes"] += 1

        for edge_kind, from_uri, to_uri in edges:
            if not from_uri or not to_uri:
                continue
            if edge_kind == "DEFINED_IN":
                s.run(
                    "MATCH (a:Symbol {project:$p, uri:$fu}), (b {project:$p, uri:$tu}) "
                    "MERGE (a)-[r:DEFINED_IN {project:$p}]->(b)",
                    p=project,
                    fu=from_uri,
                    tu=to_uri,
                )
                created["edges"] += 1
            elif edge_kind == "USES":
                s.run(
                    "MATCH (a:Symbol {project:$p, uri:$fu}), (b:Symbol {project:$p, uri:$tu}) "
                    "MERGE (a)-[r:USES {project:$p}]->(b)",
                    p=project,
                    fu=from_uri,
                    tu=to_uri,
                )
                created["edges"] += 1
            elif edge_kind == "DESCRIBED_IN":
                s.run(
                    "MATCH (a {project:$p, uri:$fu}), (b:DocSection {project:$p, uri:$tu}) "
                    "MERGE (a)-[r:DESCRIBED_IN {project:$p}]->(b)",
                    p=project,
                    fu=from_uri,
                    tu=to_uri,
                )
                created["edges"] += 1
            elif edge_kind == "REFERENCES":
                s.run(
                    "MATCH (a:DocSection {project:$p, uri:$fu}), (b {project:$p, uri:$tu}) "
                    "MERGE (a)-[r:REFERENCES {project:$p}]->(b)",
                    p=project,
                    fu=from_uri,
                    tu=to_uri,
                )
                created["edges"] += 1
            elif edge_kind == "TESTS":
                s.run(
                    "MATCH (a {project:$p, uri:$fu}), (b {project:$p, uri:$tu}) "
                    "MERGE (a)-[r:TESTS {project:$p}]->(b)",
                    p=project,
                    fu=from_uri,
                    tu=to_uri,
                )
                created["edges"] += 1
            elif edge_kind == "SIMILAR_TO":
                s.run(
                    "MATCH (a {project:$p, uri:$fu}), (b {project:$p, uri:$tu}) "
                    "MERGE (a)-[r:SIMILAR_TO {project:$p}]->(b)",
                    p=project,
                    fu=from_uri,
                    tu=to_uri,
                )
                created["edges"] += 1
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Data-driven graph projection into Neo4j (uses PG URIs)")
    parser.add_argument("--project", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    _load_env(PROJECT_ROOT / ".env")
    env = Env(
        pg_dsn=(os.getenv("PG_DSN") or os.getenv("PG_DSN_RO") or "").strip(),
        neo4j_uri=(os.getenv("NEO4J_URI") or os.getenv("NEO4J_URI_RO") or "").strip(),
        neo4j_user=(os.getenv("NEO4J_USER") or os.getenv("NEO4J_USER_RO") or "").strip(),
        neo4j_pass=(os.getenv("NEO4J_PASS") or os.getenv("NEO4J_PASS_RO") or "").strip(),
    )

    if not env.pg_dsn:
        raise RuntimeError("PG_DSN is not set")
    if not (env.neo4j_uri and env.neo4j_user and env.neo4j_pass):
        raise RuntimeError("NEO4J credentials are not set")

    graph_client = GraphClient(env.neo4j_uri, env.neo4j_user, env.neo4j_pass)
    ensure_constraints(graph_client)

    pg = PgClient(env.pg_dsn)
    ingest = IngestRepo(pg)
    code_rows = ingest.fetch_code_nodes(args.project)
    doc_rows = ingest.fetch_doc_nodes(args.project)
    symbols = ingest.fetch_symbols(args.project)
    edges = ingest.fetch_edges(args.project)

    if args.dry_run:
        summary = dry_run_summary(args.project, code_rows, doc_rows, symbols, edges)
        logger.info("graphify dry-run summary: %s", summary)
        print(summary)
    else:
        res = apply_graph(graph_client, args.project, code_rows, doc_rows, symbols, edges)
        logger.info("graphify applied: %s", res)
        print(res)


if __name__ == "__main__":
    main()
