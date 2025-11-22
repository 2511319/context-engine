from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from ..postgres import PgClient


class FeedbackRepo:
    """Data access for dp_feedback table."""

    def __init__(self, pg: PgClient) -> None:
        self.pg = pg

    def recent_feedback_for(self, project: str, task_fp: str, uris: Iterable[str]) -> List[Tuple[str, int, str]]:
        ulist = list(uris)
        if not ulist:
            return []
        placeholders = ",".join(["%s"] * len(ulist))
        sql = f"SELECT uri, label, created_at::text FROM dp_feedback WHERE project=%s AND task_fp=%s AND uri IN ({placeholders})"
        params: Tuple[Any, ...] = (project, task_fp, *ulist)
        with self.pg.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        return [(r[0], int(r[1]), r[2]) for r in rows]

    def insert_feedback(self, project: str, task_fp: str, uri: str, label: int) -> None:
        sql = "INSERT INTO dp_feedback(project, task_fp, uri, label) VALUES (%s,%s,%s,%s)"
        self.pg.execute(sql, (project, task_fp, uri, label))
