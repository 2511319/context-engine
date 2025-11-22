"""Read-only Neo4j helper."""

from __future__ import annotations

from contextlib import contextmanager

from core.dal import GraphClient

from ..deps import get_settings

_graph_client: GraphClient | None = None


def _client() -> GraphClient:
    global _graph_client
    if _graph_client is None:
        settings = get_settings()
        _graph_client = GraphClient(settings.neo4j_uri_ro, settings.neo4j_user_ro, settings.neo4j_pass_ro)
    return _graph_client


@contextmanager
def get_driver():
    """Yield a Neo4j driver with read-only credentials via DAL client."""
    client = _client()
    driver = client.driver()
    try:
        yield driver
    finally:
        driver.close()
