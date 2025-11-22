from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Dict, Iterable

try:
    from neo4j import GraphDatabase  # type: ignore
except Exception:  # pragma: no cover
    GraphDatabase = None  # type: ignore


logger = logging.getLogger(__name__)


class GraphClient:
    """Thin Neo4j client wrapper."""

    def __init__(self, uri: str, user: str, password: str) -> None:
        if not (uri and user and password):
            raise ValueError("neo4j uri/user/password are required")
        if GraphDatabase is None:
            raise RuntimeError("neo4j-driver is required")
        self.uri = uri
        self.user = user
        self.password = password

    def driver(self):
        return GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    @contextmanager
    def session(self):
        driver = self.driver()
        try:
            with driver.session() as session:
                yield session
        finally:
            driver.close()

    def run(self, cypher: str, params: Dict[str, Any] | None = None) -> Iterable[Dict[str, Any]]:
        with self.session() as session:
            result = session.run(cypher, parameters=params or {})
            for record in result:
                yield dict(record)
