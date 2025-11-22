from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from core.dal import PgClient


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlanLogEntry:
    plan_id: str
    ts: datetime
    project: str
    module: Optional[str]
    status: str
    route: Optional[str]
    latency_ms: Optional[int] = None
    source_latencies: Dict[str, Any] = field(default_factory=dict)
    result_sizes: Dict[str, Any] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    token_budget: Optional[Dict[str, Any]] = None
    detail: Dict[str, Any] = field(default_factory=dict)


def new_plan_id() -> str:
    """Generate a new plan_id (UUID4) as string."""
    return str(uuid.uuid4())


class PlanLogger:
    """Persists plan executions to Postgres and optional JSONL log."""

    def __init__(
        self,
        pg_dsn: Optional[str] = None,
        jsonl_path: Optional[Path] = None,
        pg_client: Optional[PgClient] = None,
    ) -> None:
        self.pg_dsn = pg_dsn
        self.jsonl_path = jsonl_path
        self.pg_client = pg_client or (PgClient(pg_dsn) if pg_dsn else None)

    def log(self, entry: PlanLogEntry) -> None:
        """Write the entry to Postgres (if configured) and JSONL (best effort)."""
        self._write_pg(entry)
        if self.jsonl_path:
            self._write_jsonl(self.jsonl_path, entry)

    def _write_pg(self, entry: PlanLogEntry) -> None:
        if not self.pg_client:
            return
        try:
            with self.pg_client.connect() as conn:
                with conn.cursor() as cur:
                    token_budget_json = (
                        json.dumps(entry.token_budget, ensure_ascii=False)
                        if entry.token_budget is not None
                        else None
                    )
                    cur.execute(
                        """
                        INSERT INTO plan_log (
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
                        )
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb)
                        ON CONFLICT (plan_id) DO UPDATE SET
                            ts = EXCLUDED.ts,
                            project = EXCLUDED.project,
                            module = EXCLUDED.module,
                            status = EXCLUDED.status,
                            route = EXCLUDED.route,
                            latency_ms = EXCLUDED.latency_ms,
                            source_latencies = EXCLUDED.source_latencies,
                            result_sizes = EXCLUDED.result_sizes,
                            params = EXCLUDED.params,
                            token_budget = EXCLUDED.token_budget,
                            detail = EXCLUDED.detail
                        """,
                        (
                            entry.plan_id,
                            entry.ts,
                            entry.project,
                            entry.module,
                            entry.status,
                            entry.route,
                            entry.latency_ms,
                            json.dumps(entry.source_latencies, ensure_ascii=False),
                            json.dumps(entry.result_sizes, ensure_ascii=False),
                            json.dumps(entry.params, ensure_ascii=False),
                            token_budget_json,
                            json.dumps(entry.detail, ensure_ascii=False),
                        ),
                    )
        except Exception as exc:  # pragma: no cover
            logger.exception("Failed to persist plan log entry: %s", exc)

    @staticmethod
    def _write_jsonl(log_path: Path, entry: PlanLogEntry) -> None:
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            record = {
                "ts": entry.ts.astimezone(timezone.utc).isoformat(),
                "plan_id": entry.plan_id,
                "project": entry.project,
                "module": entry.module,
                "status": entry.status,
                "route": entry.route,
                "latency_ms": entry.latency_ms,
                "source_latencies": entry.source_latencies,
                "result_sizes": entry.result_sizes,
                "params": entry.params,
                "token_budget": entry.token_budget,
                "detail": entry.detail,
            }
            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as exc:  # pragma: no cover
            logger.exception("Failed to write plan JSONL: %s", exc)
