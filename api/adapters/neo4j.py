"""Read-only Neo4j helper."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from ..deps import get_settings

try:
    from neo4j import GraphDatabase  # type: ignore
except Exception:  # pragma: no cover
    GraphDatabase = None  # type: ignore


@contextmanager
def get_driver():
    """Yield a Neo4j driver with read-only credentials."""
    if GraphDatabase is None:
        raise RuntimeError("neo4j-driver is not installed. Install 'neo4j>=5.23.0'.")
    settings = get_settings()
    driver = GraphDatabase.driver(
        settings.neo4j_uri_ro,
        auth=(settings.neo4j_user_ro, settings.neo4j_pass_ro),
        max_connection_lifetime=300,
    )
    try:
        yield driver
    finally:
        driver.close()
