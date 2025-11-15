"""Index health metrics."""

from __future__ import annotations

import time
from decimal import Decimal
from typing import Any, Dict, Iterable, Tuple

from ..adapters import postgres
from ..services import jobs as jobs_service

CACHE_TTL_SECONDS = 30
_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def _fetchone_dict(cur) -> Dict[str, Any]:
    row = cur.fetchone()
    if row is None:
        return {}
    columns = [desc[0] for desc in cur.description]
    return _normalize_numbers(dict(zip(columns, row)))


def _normalize_numbers(data: Dict[str, Any]) -> Dict[str, Any]:
    def _convert(value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, dict):
            return {k: _convert(v) for k, v in value.items()}
        return value

    return {k: _convert(v) for k, v in data.items()}


def _rows_to_dict(rows: Iterable[tuple[str, Any]]) -> Dict[str, Any]:
    return {name: (float(value) if isinstance(value, Decimal) else value) for name, value in rows}


def _table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s)", (f"public.{table_name}",))
    row = cur.fetchone()
    return bool(row and row[0])


def fetch_index_metrics(project: str) -> Dict[str, Any]:
    """Collect key metrics about indexed data."""
    now = time.time()
    cached = _CACHE.get(project)
    if cached and now - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    metrics: Dict[str, Any] = {}
    sql_chunks = """
        SELECT
            count(*) AS total,
            avg(length(content)) AS avg_len,
            min(length(content)) AS min_len,
            max(length(content)) AS max_len,
            percentile_cont(0.5) WITHIN GROUP (ORDER BY length(content)) AS p50_len,
            percentile_cont(0.9) WITHIN GROUP (ORDER BY length(content)) AS p90_len,
            sum(CASE WHEN module IS NULL OR module='' THEN 1 ELSE 0 END) AS without_module,
            count(*) - count(DISTINCT fp_sha256) AS duplicates
        FROM code_chunks
        WHERE project = %s
    """
    sql_docs = """
        SELECT
            count(*) AS total,
            avg(length(content)) AS avg_len,
            min(length(content)) AS min_len,
            max(length(content)) AS max_len,
            percentile_cont(0.5) WITHIN GROUP (ORDER BY length(content)) AS p50_len,
            percentile_cont(0.9) WITHIN GROUP (ORDER BY length(content)) AS p90_len,
            count(*) - count(DISTINCT fp_sha256) AS duplicates
        FROM doc_chunks
        WHERE project = %s
    """
    sql_symbols_total = "SELECT count(*) AS symbols FROM symbols WHERE project=%s"
    sql_symbols_by_kind = "SELECT kind, count(*) FROM symbols WHERE project=%s GROUP BY kind"
    sql_symbol_refs = """
        SELECT rel, count(*) FROM symbol_refs WHERE project=%s GROUP BY rel
    """
    sql_edges = """
        SELECT rel, count(*) AS cnt
        FROM dp_edge
        WHERE project=%s
        GROUP BY rel
    """
    sql_feedback = """
        SELECT
            sum(CASE WHEN label=1 THEN 1 ELSE 0 END) AS positive,
            sum(CASE WHEN label=-1 THEN 1 ELSE 0 END) AS negative,
            count(*) AS total
        FROM dp_feedback
        WHERE project=%s
    """
    sql_doc_kinds = "SELECT kind, count(*) FROM doc_chunks WHERE project=%s GROUP BY kind"
    sql_near_dup = "SELECT count(*) FROM near_dup WHERE project=%s"

    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql_chunks, (project,))
            metrics["code_chunks"] = _fetchone_dict(cur)

            cur.execute(sql_docs, (project,))
            doc_stats = _fetchone_dict(cur)
            cur.execute(sql_doc_kinds, (project,))
            doc_stats["by_kind"] = _rows_to_dict(cur.fetchall())
            metrics["doc_chunks"] = doc_stats

            cur.execute(sql_symbols_total, (project,))
            total_symbols = cur.fetchone()
            cur.execute(sql_symbols_by_kind, (project,))
            symbol_by_kind = _rows_to_dict(cur.fetchall())
            metrics["symbols"] = {
                "total": total_symbols[0] if total_symbols else 0,
                "by_kind": symbol_by_kind,
            }

            cur.execute(sql_symbol_refs, (project,))
            metrics["symbol_refs"] = _rows_to_dict(cur.fetchall())

            cur.execute(sql_edges, (project,))
            metrics["edges"] = _rows_to_dict(cur.fetchall())

            cur.execute(sql_feedback, (project,))
            feedback = _fetchone_dict(cur)
            total_feedback = feedback.get("total") or 0
            positive = feedback.get("positive") or 0
            feedback["ctr_positive"] = (positive / total_feedback) if total_feedback else 0.0
            metrics["feedback"] = feedback

            if _table_exists(cur, "near_dup"):
                cur.execute(sql_near_dup, (project,))
                count_row = cur.fetchone()
                metrics["near_duplicates"] = {"pairs": count_row[0] if count_row else 0}
            else:
                metrics["near_duplicates"] = {"pairs": 0, "note": "near_dup table not found"}

    metrics["jobs"] = _job_summary(project)
    _CACHE[project] = (now, metrics)
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
