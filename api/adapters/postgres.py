"""Read-only Postgres helper."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from core.dal import PgClient

from ..deps import get_settings


_pg_client: PgClient | None = None


def _client() -> PgClient:
    global _pg_client
    if _pg_client is None:
        settings = get_settings()
        _pg_client = PgClient(settings.pg_dsn_ro)
    return _pg_client


@contextmanager
def get_connection() -> Iterator:
    """Yield a read-only Postgres connection from DAL client."""
    conn = _client().connect()
    try:
        yield conn
    finally:
        conn.close()
