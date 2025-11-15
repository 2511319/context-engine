from __future__ import annotations

from tools.task_fp import compute_task_fp


def test_compute_task_fp_stable_normalization() -> None:
    a = "Добавь  эндпоинт\tавторизации\nmini-app"
    b = "добавь эндпоинт авторизации mini-app"
    assert compute_task_fp(a) == compute_task_fp(b)


def test_compute_task_fp_errors() -> None:
    import pytest

    with pytest.raises(ValueError):
        compute_task_fp("")
    with pytest.raises(ValueError):
        compute_task_fp("\n\t  ")
