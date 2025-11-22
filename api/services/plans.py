"""Logic for reading plan logs and exposes SSE-friendly payloads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.dal import PgClient
from core.dal.repos import PlanRepo

from ..deps import get_settings

_plan_repo: PlanRepo | None = None


def _repo() -> PlanRepo:
    global _plan_repo
    if _plan_repo is None:
        settings = get_settings()
        _plan_repo = PlanRepo(PgClient(settings.pg_dsn_ro))
    return _plan_repo


@dataclass(slots=True)
class PlanRecordDTO:
    """Lightweight representation of a plan_log entry."""

    plan_id: str
    ts: datetime
    project: str
    module: str | None
    status: str
    route: str | None
    latency_ms: int | None
    source_latencies: Dict[str, Any]
    result_sizes: Dict[str, Any]
    params: Dict[str, Any]
    token_budget: Dict[str, Any] | None
    detail: Dict[str, Any]


def fetch_recent_plans(limit: int = 50, project: Optional[str] = None, offset: int = 0) -> List[PlanRecordDTO]:
    """Return latest plan_log entries ordered by timestamp desc."""
    records: List[PlanRecordDTO] = []
    rows = _repo().fetch_recent(limit=limit, project=project, offset=offset)
    for row in rows:
        records.append(
            PlanRecordDTO(
                plan_id=row[0],
                ts=row[1],
                project=row[2],
                module=row[3],
                status=row[4],
                route=row[5],
                latency_ms=row[6],
                source_latencies=row[7] or {},
                result_sizes=row[8] or {},
                params=row[9] or {},
                token_budget=row[10],
                detail=row[11] or {},
            )
        )
    return records


def fetch_plan(plan_id: str) -> Optional[PlanRecordDTO]:
    row = _repo().fetch_one(plan_id)
    if not row:
        return None
    return PlanRecordDTO(
        plan_id=row[0],
        ts=row[1],
        project=row[2],
        module=row[3],
        status=row[4],
        route=row[5],
        latency_ms=row[6],
        source_latencies=row[7] or {},
        result_sizes=row[8] or {},
        params=row[9] or {},
        token_budget=row[10],
        detail=row[11] or {},
    )
