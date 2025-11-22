from __future__ import annotations

import logging
from typing import Any, Iterable, Sequence

try:
    import psycopg
except Exception:  # pragma: no cover
    psycopg = None  # type: ignore


logger = logging.getLogger(__name__)


class PgClient:
    """Thin Postgres client with autocommit connections."""

    def __init__(self, dsn: str) -> None:
        if not dsn:
            raise ValueError("pg dsn must be provided")
        if psycopg is None:
            raise RuntimeError("psycopg (psycopg3) is required")
        self.dsn = dsn

    def connect(self):  # type: ignore[no-untyped-def]
        return psycopg.connect(self.dsn, autocommit=True)

    @staticmethod
    def set_hnsw(cur: "psycopg.Cursor[Any]", ef_search: int = 40) -> None:
        try:
            cur.execute(f"SET hnsw.ef_search = {int(ef_search)}")
        except Exception as exc:
            logger.warning("Failed to set hnsw.ef_search: %s", exc)

    def execute(self, sql: str, params: Iterable[Any] | None = None) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params or ()))

    def query(self, sql: str, params: Iterable[Any] | None = None) -> list[Sequence[Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params or ()))
                return cur.fetchall()
