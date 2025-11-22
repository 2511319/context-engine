from __future__ import annotations

import time
from decimal import Decimal
from typing import Any, Dict, Iterable, Tuple

from ..postgres import PgClient


class StatsRepo:
    """Aggregated metrics reader for indexed data."""

    def __init__(self, pg: PgClient) -> None:
        self.pg = pg
        self._cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}

    @staticmethod
    def _normalize_numbers(data: Dict[str, Any]) -> Dict[str, Any]:
        def _convert(value: Any) -> Any:
            if isinstance(value, Decimal):
                return float(value)
            if isinstance(value, dict):
                return {k: _convert(v) for k, v in value.items()}
            return value

        return {k: _convert(v) for k, v in data.items()}

    @staticmethod
    def _rows_to_dict(rows: Iterable[Tuple[str, Any]]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for name, value in rows:
            out[name] = float(value) if isinstance(value, Decimal) else value
        return out

    def _table_exists(self, cur, table_name: str) -> bool:  # type: ignore[no-untyped-def]
        cur.execute("SELECT to_regclass(%s)", (f"public.{table_name}",))
        row = cur.fetchone()
        return bool(row and row[0])

    def fetch_metrics(self, project: str, ttl_seconds: int = 30) -> Dict[str, Any]:
        now = time.time()
        cached = self._cache.get(project)
        if cached and now - cached[0] < ttl_seconds:
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
        sql_symbol_refs = "SELECT rel, count(*) FROM symbol_refs WHERE project=%s GROUP BY rel"
        sql_edges = (
            "SELECT COALESCE(edge_kind, rel) AS edge_kind, count(*) AS cnt "
            "FROM dp_edge WHERE project=%s GROUP BY 1"
        )
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

        with self.pg.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql_chunks, (project,))
                metrics["code_chunks"] = self._normalize_numbers(dict(zip([desc[0] for desc in cur.description], cur.fetchone() or [])))

                cur.execute(sql_docs, (project,))
                doc_stats = self._normalize_numbers(dict(zip([desc[0] for desc in cur.description], cur.fetchone() or [])))
                cur.execute(sql_doc_kinds, (project,))
                doc_stats["by_kind"] = self._rows_to_dict(cur.fetchall())
                metrics["doc_chunks"] = doc_stats

                cur.execute(sql_symbols_total, (project,))
                total_symbols = cur.fetchone()
                cur.execute(sql_symbols_by_kind, (project,))
                symbol_by_kind = self._rows_to_dict(cur.fetchall())
                metrics["symbols"] = {
                    "total": total_symbols[0] if total_symbols else 0,
                    "by_kind": symbol_by_kind,
                }

                cur.execute(sql_symbol_refs, (project,))
                metrics["symbol_refs"] = self._rows_to_dict(cur.fetchall())

                cur.execute(sql_edges, (project,))
                metrics["edges"] = self._rows_to_dict(cur.fetchall())

                cur.execute(sql_feedback, (project,))
                feedback_row = cur.fetchone()
                raw_feedback = dict(zip([desc[0] for desc in cur.description], feedback_row or []))
                feedback = self._normalize_numbers(raw_feedback)
                total_feedback = feedback.get("total") or 0
                positive = feedback.get("positive") or 0
                feedback["ctr_positive"] = (positive / total_feedback) if total_feedback else 0.0
                metrics["feedback"] = feedback

                if self._table_exists(cur, "near_dup"):
                    cur.execute(sql_near_dup, (project,))
                    count_row = cur.fetchone()
                    metrics["near_duplicates"] = {"pairs": count_row[0] if count_row else 0}
                else:
                    metrics["near_duplicates"] = {"pairs": 0, "note": "near_dup table not found"}

        self._cache[project] = (now, metrics)
        return metrics
