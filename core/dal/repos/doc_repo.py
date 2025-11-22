from __future__ import annotations

from typing import Iterable, List, Sequence

from ..postgres import PgClient
from ..types import ChunkRow


class DocRepo:
    """Data access for doc_chunks."""

    def __init__(self, pg: PgClient) -> None:
        self.pg = pg

    @staticmethod
    def _vector_literal(vec: Sequence[float]) -> str:
        return "[" + ",".join(f"{v:.6f}" for v in vec) + "]"

    def topk_vector(self, project: str, embedding: Sequence[float], k: int) -> List[ChunkRow]:
        sql = (
            "SELECT id, project, doc_name, section, kind, content, commit_sha, chunk_id, fp_sha256, "
            " embedding <=> %s::vector AS dist "
            "FROM doc_chunks WHERE project=%s AND embedding IS NOT NULL "
            "ORDER BY embedding <=> %s::vector ASC LIMIT %s"
        )
        lit = self._vector_literal(embedding)
        with self.pg.connect() as conn:
            with conn.cursor() as cur:
                self.pg.set_hnsw(cur)
                cur.execute(sql, (lit, project, lit, k))
                rows = cur.fetchall()
        return [
            ChunkRow(
                id=r[0],
                project=r[1],
                doc_name=r[2],
                section=r[3],
                kind=r[4],
                content=r[5],
                commit_sha=r[6],
                chunk_id=r[7],
                fp_sha256=r[8],
                dist=r[9],
            )
            for r in rows
        ]

    def topk_lex(self, project: str, query: str, k: int, lex_cfg: str = "simple") -> List[ChunkRow]:
        sql = (
            "SELECT id, project, doc_name, section, content, commit_sha, chunk_id, fp_sha256, "
            " ts_rank_cd(lex, plainto_tsquery(%s, %s)) AS rank "
            "FROM doc_chunks WHERE project=%s AND lex IS NOT NULL AND lex @@ plainto_tsquery(%s, %s) "
            "ORDER BY ts_rank_cd(lex, plainto_tsquery(%s, %s)) DESC LIMIT %s"
        )
        with self.pg.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (lex_cfg, query, project, lex_cfg, query, lex_cfg, query, k))
                rows = cur.fetchall()
        return [
            ChunkRow(
                id=r[0],
                project=r[1],
                doc_name=r[2],
                section=r[3],
                content=r[4],
                commit_sha=r[5],
                chunk_id=r[6],
                fp_sha256=r[7],
                rank=r[8],
            )
            for r in rows
        ]
