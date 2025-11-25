from __future__ import annotations

import argparse
import logging
import math
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple, Union
import json
import ast

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.dal import PgClient
from core.dal.repos import IngestRepo

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("context_engine.tools.build_similarity")


def _load_env(env_path: Path) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        os.environ[key.strip()] = value.strip()


def _as_list(vec: object) -> List[float]:
    if vec is None:
        return []
    if isinstance(vec, (str, bytes)):
        try:
            parsed = json.loads(vec)
        except Exception:
            parsed = ast.literal_eval(vec.decode() if isinstance(vec, bytes) else vec)
        return [float(v) for v in list(parsed)]
    if hasattr(vec, "tolist"):
        return [float(v) for v in list(vec.tolist())]  # type: ignore[arg-type]
    if isinstance(vec, memoryview):
        return [float(v) for v in list(vec.tolist())]  # type: ignore[arg-type]
    if isinstance(vec, list):
        return [float(v) for v in vec]
    return [float(v) for v in list(vec)]  # type: ignore[arg-type]


def _mean_vector(vectors: List[List[float]]) -> List[float]:
    if not vectors:
        return []
    dim = len(vectors[0])
    acc = [0.0] * dim
    for vec in vectors:
        for i, v in enumerate(vec):
            acc[i] += v
    inv = 1.0 / len(vectors)
    return [v * inv for v in acc]


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _topk(edges: List[Tuple[str, List[float]]], top_k: int, min_score: float) -> List[Tuple[str, str, float]]:
    results: List[Tuple[str, str, float]] = []
    for idx, (src_uri, src_vec) in enumerate(edges):
        scored: List[Tuple[str, float]] = []
        for jdx, (dst_uri, dst_vec) in enumerate(edges):
            if idx == jdx:
                continue
            score = _cosine(src_vec, dst_vec)
            if score >= min_score:
                scored.append((dst_uri, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        for to_uri, score in scored[:top_k]:
            results.append((src_uri, to_uri, score))
    return results


def _fetch_doc_embeddings(repo: IngestRepo, project: str) -> List[Tuple[str, List[float]]]:
    sql = "SELECT uri, embedding FROM doc_chunks WHERE project=%s AND embedding IS NOT NULL"
    rows: List[Sequence[object]] = repo._fetchall(sql, (project,))  # type: ignore[attr-defined]
    return [(uri, _as_list(vec)) for uri, vec in rows if vec is not None]


def _fetch_code_embeddings(repo: IngestRepo, project: str) -> List[Tuple[str, List[float]]]:
    sql = "SELECT uri, embedding FROM code_chunks WHERE project=%s AND embedding IS NOT NULL"
    rows: List[Sequence[object]] = repo._fetchall(sql, (project,))  # type: ignore[attr-defined]
    grouped: defaultdict[str, List[List[float]]] = defaultdict(list)
    for uri, vec in rows:
        if vec is None:
            continue
        grouped[str(uri)].append(_as_list(vec))
    averaged = [(uri, _mean_vector(vs)) for uri, vs in grouped.items() if vs]
    return averaged


def main() -> None:
    parser = argparse.ArgumentParser(description="Build SIMILAR_TO edges from embeddings")
    parser.add_argument("--project", required=True)
    parser.add_argument("--kind", choices=["doc", "code", "both"], default="both")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--min-score", type=float, default=0.8)
    args = parser.parse_args()

    _load_env(PROJECT_ROOT / ".env")
    pg_dsn = (os.getenv("PG_DSN") or os.getenv("PG_DSN_RO") or "").strip()
    if not pg_dsn:
        raise RuntimeError("PG_DSN is not set")

    pg = PgClient(pg_dsn)
    repo = IngestRepo(pg)

    include_docs = args.kind in {"doc", "both"}
    include_code = args.kind in {"code", "both"}

    with repo.cursor() as cur:
        repo.delete_edges_by_kind(args.project, ["SIMILAR_TO"], cur=cur)
        total_inserted = 0

        if include_docs:
            doc_embeddings = _fetch_doc_embeddings(repo, args.project)
            doc_pairs = _topk(doc_embeddings, args.top_k, args.min_score)
            for src, dst, _ in doc_pairs:
                repo.insert_edge(args.project, "SIMILAR_TO", src, dst, src, dst, cur=cur)
            total_inserted += len(doc_pairs)
            logger.info("doc SIMILAR_TO inserted: %d", len(doc_pairs))

        if include_code:
            code_embeddings = _fetch_code_embeddings(repo, args.project)
            code_pairs = _topk(code_embeddings, args.top_k, args.min_score)
            for src, dst, _ in code_pairs:
                repo.insert_edge(args.project, "SIMILAR_TO", src, dst, src, dst, cur=cur)
            total_inserted += len(code_pairs)
            logger.info("code SIMILAR_TO inserted: %d", len(code_pairs))

        logger.info("SIMILAR_TO rebuild done: %d edges", total_inserted)


if __name__ == "__main__":
    main()
