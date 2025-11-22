from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Tuple

from core.feedback import biases_for_uris
from core.dal.repos.feedback_repo import FeedbackRepo


@dataclass
class FeedbackEffect:
    pin_bias: float = 0.0
    forget_penalty: float = 0.0


def get_feedback_effects(
    feedback_repo: FeedbackRepo,
    project: str,
    task_fp: str | None,
    uris: Iterable[str],
    now: dt.datetime | None = None,
) -> Dict[str, FeedbackEffect]:
    """
    Вернуть эффекты feedback по URI.

    При отсутствии task_fp или пустом списке возвращает пустой словарь.
    """
    ulist = list(uris)
    if not task_fp or not ulist:
        return {}
    biases: Dict[str, Tuple[float, float]] = biases_for_uris(feedback_repo, project, task_fp, ulist, now=now)
    return {u: FeedbackEffect(pin_bias=b, forget_penalty=p) for u, (b, p) in biases.items()}


def aggregate_by_module(
    uri_effects: Mapping[str, FeedbackEffect],
    uri_to_module: Mapping[str, str],
) -> Dict[str, FeedbackEffect]:
    """
    Собрать эффекты на уровне модулей.

    Стратегия: усреднение по URI данного модуля (более стабильный эффект).
    """
    acc: Dict[str, Tuple[float, float, int]] = {}
    for uri, eff in uri_effects.items():
        module = uri_to_module.get(uri)
        if not module:
            continue
        pin_sum, pen_sum, cnt = acc.get(module, (0.0, 0.0, 0))
        acc[module] = (pin_sum + eff.pin_bias, pen_sum + eff.forget_penalty, cnt + 1)
    out: Dict[str, FeedbackEffect] = {}
    for module, (pin_sum, pen_sum, cnt) in acc.items():
        if cnt == 0:
            continue
        out[module] = FeedbackEffect(pin_bias=pin_sum / cnt, forget_penalty=pen_sum / cnt)
    return out
