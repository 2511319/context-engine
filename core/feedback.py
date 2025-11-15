from __future__ import annotations

import datetime as dt
from typing import Dict, Iterable, Tuple

from .pg import PgClient

HALF_LIFE_DAYS = 14.0
MAX_ABS = 0.25
PIN_BIAS = 0.10
FORGET_PENALTY = 0.20


def _decay_factor(created_at_iso: str, now: dt.datetime) -> float:
    try:
        created = dt.datetime.fromisoformat(created_at_iso.replace("Z", "+00:00"))
    except Exception:
        return 1.0
    age_days = (now - created).total_seconds() / 86400.0
    return 0.5 ** (age_days / HALF_LIFE_DAYS)


def biases_for_uris(pg: PgClient, project: str, task_fp: str, uris: Iterable[str], now: dt.datetime | None = None) -> Dict[str, Tuple[float, float]]:
    """
    Вернуть словарь uri -> (bias_pin, penalty_neg) с экспоненциальным декеем и ограничением |bias|<=0.25.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    rows = pg.recent_feedback_for(project, task_fp, list(uris))
    pos: Dict[str, float] = {}
    neg: Dict[str, float] = {}
    for uri, label, created_at in rows:
        decay = _decay_factor(created_at, now)
        if label > 0:
            pos[uri] = pos.get(uri, 0.0) + decay
        elif label < 0:
            neg[uri] = neg.get(uri, 0.0) + decay
    out: Dict[str, Tuple[float, float]] = {}
    for u in uris:
        b = PIN_BIAS * pos.get(u, 0.0)
        p = FORGET_PENALTY * neg.get(u, 0.0)
        # clamp combined magnitude
        total = b - p
        if total > MAX_ABS:
            b, p = MAX_ABS, 0.0
        elif total < -MAX_ABS:
            b, p = 0.0, MAX_ABS
        out[u] = (b, p)
    return out
