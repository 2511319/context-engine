from __future__ import annotations

from typing import Any, Dict, List

from api.services import health as health_service
from core.dal.repos.stats_repo import StatsRepo


class StubCursor:
    def __init__(self, responses: List[Dict[str, Any]]) -> None:
        self.responses = responses
        self.index = 0
        self.current: Dict[str, Any] = {}
        self.description: list = []

    def __enter__(self) -> "StubCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, sql: str, params=None) -> None:
        if self.index >= len(self.responses):
            raise AssertionError("No stubbed response for SQL query")
        self.current = self.responses[self.index]
        self.index += 1
        self.description = self.current.get("description", [])

    def fetchone(self):
        return self.current.get("fetchone")

    def fetchall(self):
        return self.current.get("fetchall", [])


class StubConnection:
    def __init__(self, responses: List[Dict[str, Any]]) -> None:
        self.responses = responses

    def __enter__(self) -> "StubConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def cursor(self) -> StubCursor:
        return StubCursor(self.responses)


def _stubbed_responses() -> List[Dict[str, Any]]:
    return [
        {
            "description": [
                ("total",),
                ("avg_len",),
                ("min_len",),
                ("max_len",),
                ("p50_len",),
                ("p90_len",),
                ("without_module",),
                ("duplicates",),
            ],
            "fetchone": (100, 120.5, 10, 400, 110, 300, 5, 2),
        },
        {
            "description": [
                ("total",),
                ("avg_len",),
                ("min_len",),
                ("max_len",),
                ("p50_len",),
                ("p90_len",),
                ("duplicates",),
            ],
            "fetchone": (50, 80.0, 20, 200, 75, 150, 1),
        },
        {"fetchall": [("doc", 40), ("spec", 10)]},
        {"fetchone": (7,)},
        {"fetchall": [("class", 5), ("func", 2)]},
        {"fetchall": [("REFERENCES", 11)]},
        {"fetchall": [("IMPLEMENTS", 3), ("DESCRIBED_IN", 4)]},
        {
            "description": [("positive",), ("negative",), ("total",)],
            "fetchone": (6, 2, 10),
        },
        {"fetchone": ("near_dup",)},  # table exists
        {"fetchone": (4,)},
    ]

class StubPg:
    def __init__(self, responses: List[Dict[str, Any]]) -> None:
        self.responses = responses
        self.calls = 0

    def connect(self) -> StubConnection:
        self.calls += 1
        return StubConnection(list(self.responses))

def _setup_repo() -> tuple[StatsRepo, StubPg]:
    pg = StubPg(_stubbed_responses())
    return StatsRepo(pg), pg


def test_fetch_index_metrics_compiles_extended_stats(monkeypatch):
    repo, pg = _setup_repo()
    health_service._stats_repo = repo  # type: ignore[attr-defined]
    monkeypatch.setattr(health_service.jobs_service, "list_jobs", lambda project: [{"job_id": "job-1", "status": "success"}])

    metrics = health_service.fetch_index_metrics("context_engine")

    assert metrics["code_chunks"]["total"] == 100
    assert metrics["code_chunks"]["p50_len"] == 110.0
    assert metrics["doc_chunks"]["by_kind"]["doc"] == 40
    assert metrics["symbols"]["total"] == 7
    assert metrics["symbols"]["by_kind"]["class"] == 5
    assert metrics["symbol_refs"]["REFERENCES"] == 11
    assert metrics["edges"]["IMPLEMENTS"] == 3
    assert metrics["feedback"]["ctr_positive"] == 0.6
    assert metrics["near_duplicates"]["pairs"] == 4
    assert metrics["jobs"]["total"] == 1
    assert pg.calls == 1
    health_service._stats_repo = None  # type: ignore[attr-defined]


def test_fetch_index_metrics_uses_cache(monkeypatch):
    repo, pg = _setup_repo()
    health_service._stats_repo = repo  # type: ignore[attr-defined]
    monkeypatch.setattr(health_service.jobs_service, "list_jobs", lambda project: [])

    first = health_service.fetch_index_metrics("context_engine")
    second = health_service.fetch_index_metrics("context_engine")

    assert first is second
    assert pg.calls == 1
    health_service._stats_repo = None  # type: ignore[attr-defined]
