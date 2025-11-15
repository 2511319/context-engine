from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import psycopg
except Exception:  # pragma: no cover
    psycopg = None  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class PgRow:
    id: int
    project: str
    path: Optional[str] = None
    module: Optional[str] = None
    doc_name: Optional[str] = None
    section: Optional[str] = None
    content: str = ""
    commit_sha: Optional[str] = None
    chunk_id: Optional[str] = None
    fp_sha256: Optional[str] = None
    dist: Optional[float] = None
    rank: Optional[float] = None


class PgClient:
    def __init__(self, dsn: str) -> None:
        if psycopg is None:
            raise RuntimeError("psycopg (psycopg3) is required")
        self.dsn = dsn

    def connect(self):  # type: ignore[no-untyped-def]
        return psycopg.connect(self.dsn, autocommit=True)

    def set_hnsw(self, cur: "psycopg.Cursor[Any]", ef_search: int = 40) -> None:
        try:
            cur.execute(f"SET hnsw.ef_search = {int(ef_search)}")
        except Exception as exc:
            logger.warning("Failed to set hnsw.ef_search: %s", exc)

    @staticmethod
    def _vector_literal(vec: Sequence[float]) -> str:
        return "[" + ",".join(f"{v:.6f}" for v in vec) + "]"

    # ---------- Vector top-K ----------
    def topk_vector_code(self, query_vec: Sequence[float], project: str, k: int) -> List[PgRow]:
        sql = (
            "SELECT id, project, path, module, content, commit_sha, chunk_id, fp_sha256, "
            " embedding <=> %s::vector AS dist "
            "FROM code_chunks WHERE project=%s AND embedding IS NOT NULL "
            "ORDER BY embedding <=> %s::vector ASC LIMIT %s"
        )
        lit = self._vector_literal(query_vec)
        with self.connect() as conn:
            with conn.cursor() as cur:
                self.set_hnsw(cur)
                cur.execute(sql, (lit, project, lit, k))
                rows = cur.fetchall()
        out: List[PgRow] = []
        for r in rows:
            out.append(
                PgRow(
                    id=r[0], project=r[1], path=r[2], module=r[3], content=r[4], commit_sha=r[5], chunk_id=r[6], fp_sha256=r[7], dist=r[8]
                )
            )
        return out

    def topk_vector_docs(self, query_vec: Sequence[float], project: str, k: int) -> List[PgRow]:
        sql = (
            "SELECT id, project, doc_name, section, kind, content, commit_sha, chunk_id, fp_sha256, "
            " embedding <=> %s::vector AS dist "
            "FROM doc_chunks WHERE project=%s AND embedding IS NOT NULL "
            "ORDER BY embedding <=> %s::vector ASC LIMIT %s"
        )
        lit = self._vector_literal(query_vec)
        with self.connect() as conn:
            with conn.cursor() as cur:
                self.set_hnsw(cur)
                cur.execute(sql, (lit, project, lit, k))
                rows = cur.fetchall()
        out: List[PgRow] = []
        for r in rows:
            out.append(
                PgRow(
                    id=r[0], project=r[1], doc_name=r[2], section=r[3], content=r[5], commit_sha=r[6], chunk_id=r[7], fp_sha256=r[8], dist=r[9]
                )
            )
        return out

    # ---------- Lexical top-K ----------
    def topk_lex_code(self, query: str, project: str, k: int, lex_cfg: str = "simple") -> List[PgRow]:
        sql = (
            "SELECT id, project, path, module, content, commit_sha, chunk_id, fp_sha256, "
            " ts_rank_cd(lex, plainto_tsquery(%s, %s)) AS rank "
            "FROM code_chunks WHERE project=%s AND lex IS NOT NULL AND lex @@ plainto_tsquery(%s, %s) "
            "ORDER BY ts_rank_cd(lex, plainto_tsquery(%s, %s)) DESC LIMIT %s"
        )
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (lex_cfg, query, project, lex_cfg, query, lex_cfg, query, k))
                rows = cur.fetchall()
        out: List[PgRow] = []
        for r in rows:
            out.append(PgRow(id=r[0], project=r[1], path=r[2], module=r[3], content=r[4], commit_sha=r[5], chunk_id=r[6], fp_sha256=r[7], rank=r[8]))
        return out

    def topk_lex_docs(self, query: str, project: str, k: int, lex_cfg: str = "simple") -> List[PgRow]:
        sql = (
            "SELECT id, project, doc_name, section, content, commit_sha, chunk_id, fp_sha256, "
            " ts_rank_cd(lex, plainto_tsquery(%s, %s)) AS rank "
            "FROM doc_chunks WHERE project=%s AND lex IS NOT NULL AND lex @@ plainto_tsquery(%s, %s) "
            "ORDER BY ts_rank_cd(lex, plainto_tsquery(%s, %s)) DESC LIMIT %s"
        )
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (lex_cfg, query, project, lex_cfg, query, lex_cfg, query, k))
                rows = cur.fetchall()
        out: List[PgRow] = []
        for r in rows:
            out.append(PgRow(id=r[0], project=r[1], doc_name=r[2], section=r[3], content=r[4], commit_sha=r[5], chunk_id=r[6], fp_sha256=r[7], rank=r[8]))
        return out

    def list_modules(self, project: str, limit: int = 2000) -> List[str]:
        sql = "SELECT DISTINCT module FROM code_chunks WHERE project=%s AND module IS NOT NULL LIMIT %s"
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (project, limit))
                rows = cur.fetchall()
        return [r[0] for r in rows if r and r[0]]

    def recent_feedback_for(self, project: str, task_fp: str, uris: Iterable[str]) -> List[Tuple[str, int, str]]:
        ulist = list(uris)
        if not ulist:
            return []
        placeholders = ",".join(["%s"] * len(ulist))
        sql = f"SELECT uri, label, created_at::text FROM dp_feedback WHERE project=%s AND task_fp=%s AND uri IN ({placeholders})"
        params: Tuple[Any, ...] = (project, task_fp, *ulist)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        return [(r[0], int(r[1]), r[2]) for r in rows]
