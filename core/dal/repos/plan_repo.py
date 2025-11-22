from __future__ import annotations

from typing import Any, List, Optional, Sequence

from ..postgres import PgClient


class PlanRepo:
    """Read-only access to plan_log."""

    def __init__(self, pg: PgClient) -> None:
        self.pg = pg

    def fetch_recent(self, limit: int = 50, project: Optional[str] = None, offset: int = 0) -> List[Sequence[Any]]:
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
        where = ""
        if project:
            where = "WHERE project=%s"
            params.append(project)
        sql = f"{base_sql} {where} ORDER BY ts DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        return self.pg.query(sql, params)

    def fetch_one(self, plan_id: str) -> Optional[Sequence[Any]]:
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
            LIMIT 1
        """
        rows = self.pg.query(sql, (plan_id,))
        return rows[0] if rows else None
