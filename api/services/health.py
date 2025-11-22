"""Index health metrics."""

from __future__ import annotations

from typing import Any, Dict

from core.dal import PgClient
from core.dal.repos import StatsRepo

from ..deps import get_settings
from ..services import jobs as jobs_service

_stats_repo: StatsRepo | None = None


def _repo() -> StatsRepo:
    global _stats_repo
    if _stats_repo is None:
        settings = get_settings()
        _stats_repo = StatsRepo(PgClient(settings.pg_dsn_ro))
    return _stats_repo


def fetch_index_metrics(project: str) -> Dict[str, Any]:
    """Collect key metrics about indexed data."""
    metrics = _repo().fetch_metrics(project)
    metrics["jobs"] = _job_summary(project)
    return metrics


def _job_summary(project: str) -> Dict[str, Any]:
    jobs = jobs_service.list_jobs(project)
    by_status: Dict[str, int] = {}
    for job in jobs:
        status = str(job.get("status") or "unknown")
        by_status[status] = by_status.get(status, 0) + 1
    latest = jobs[0] if jobs else None
    latest_brief = None
    if latest:
        latest_brief = {
            "job_id": latest.get("job_id"),
            "name": latest.get("name"),
            "status": latest.get("status"),
            "started_at": latest.get("started_at"),
        }
    return {"total": len(jobs), "by_status": by_status, "latest": latest_brief}
