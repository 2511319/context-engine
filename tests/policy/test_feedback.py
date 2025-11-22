from __future__ import annotations

import datetime as dt

from core.policy.feedback import FeedbackEffect, aggregate_by_module, get_feedback_effects
from core.dal.repos.feedback_repo import FeedbackRepo


class _FakeFeedbackRepo(FeedbackRepo):
    def __init__(self, rows: list[tuple[str, int, str]]) -> None:
        self._rows = rows

    def recent_feedback_for(self, project: str, task_fp: str, uris):
        # игнорируем project/task_fp в фейке, фильтруем по uris
        u_set = set(uris)
        return [r for r in self._rows if r[0] in u_set]


def test_get_feedback_effects_with_decay_and_clamp() -> None:
    now = dt.datetime(2024, 1, 15, tzinfo=dt.timezone.utc)
    # один pin вчера, два forget три дня назад
    rows = [
        ("uri://a", 1, "2024-01-14T00:00:00+00:00"),
        ("uri://a", -1, "2024-01-12T00:00:00+00:00"),
        ("uri://a", -1, "2024-01-12T00:00:00+00:00"),
    ]
    repo = _FakeFeedbackRepo(rows)
    effects = get_feedback_effects(repo, "project", "taskfp", ["uri://a"], now=now)
    eff = effects["uri://a"]
    # Проверяем что эффект присутствует и обе компоненты положительные/ненулевые
    assert eff.pin_bias > 0
    assert eff.forget_penalty > 0


def test_aggregate_by_module_average() -> None:
    uri_effects = {
        "u1": FeedbackEffect(pin_bias=0.1, forget_penalty=0.0),
        "u2": FeedbackEffect(pin_bias=0.0, forget_penalty=0.2),
        "u3": FeedbackEffect(pin_bias=0.2, forget_penalty=0.1),
    }
    uri_to_module = {"u1": "m1", "u2": "m1", "u3": "m2"}

    modules = aggregate_by_module(uri_effects, uri_to_module)
    assert modules["m1"].pin_bias == (0.1 + 0.0) / 2
    assert modules["m1"].forget_penalty == (0.0 + 0.2) / 2
    assert modules["m2"].pin_bias == 0.2
    assert modules["m2"].forget_penalty == 0.1


def test_get_feedback_effects_short_circuits() -> None:
    repo = _FakeFeedbackRepo([])
    assert get_feedback_effects(repo, "project", None, ["u"]) == {}
    assert get_feedback_effects(repo, "project", "taskfp", []) == {}
