"""Read-only Postgres helper."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg

from ..deps import get_settings


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    """Yield a read-only psycopg connection."""
    settings = get_settings()
    conn = psycopg.connect(settings.pg_dsn_ro, autocommit=True)
    try:
        yield conn
    finally:
        conn.close()
