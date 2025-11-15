"""Logic for reading plan logs and exposes SSE-friendly payloads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..adapters import postgres


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


def fetch_recent_plans(limit: int = 50, project: Optional[str] = None) -> List[PlanRecordDTO]:
    """Return latest plan_log entries ordered by timestamp desc."""
    base_sql = """
        SELECT
            plan_id,
            ts,
            project,
            module,
            status,
            route,
            latency_ms,
            source_latencies,
            result_sizes,
            params,
            token_budget,
            detail
        FROM plan_log
    """
    params: list[Any] = []
    where_clause = ""
    if project:
        where_clause = "WHERE project=%s"
        params.append(project)
    sql = f"{base_sql} {where_clause} ORDER BY ts DESC LIMIT %s"
    params.append(limit)
    records: List[PlanRecordDTO] = []
    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            for row in cur.fetchall():
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
    sql = """
        SELECT
            plan_id,
            ts,
            project,
            module,
            status,
            route,
            latency_ms,
            source_latencies,
            result_sizes,
            params,
            token_budget,
            detail
        FROM plan_log
        WHERE plan_id=%s
    """
    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (plan_id,))
            row = cur.fetchone()
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
