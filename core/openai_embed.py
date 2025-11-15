from __future__ import annotations

import json
import logging
from typing import Iterable, List, Optional

import requests

logger = logging.getLogger(__name__)


def embed_batch(texts: Iterable[str], model: str, dims: int, api_key: Optional[str], timeout_sec: int = 60) -> List[List[float]]:
    """
    Получить эмбеддинги пачкой через OpenAI Embeddings API.

    Args:
        texts: Итератор строк для кодирования.
        model: Имя модели (например, "text-embedding-3-large").
        dims: Желаемое число измерений (например, 1024).
        api_key: Ключ OpenAI.
        timeout_sec: Таймаут запроса.

    Returns:
        Список векторов (list[float]) по порядку входа.

    Raises:
        RuntimeError: при отсутствии api_key или ошибках сети.
    """
    arr = list(texts)
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    if not arr:
        return []
    url = "https://api.openai.com/v1/embeddings"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "input": arr, "dimensions": dims}
    try:
        resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=timeout_sec)
        resp.raise_for_status()
        data = resp.json()
        vectors = [item["embedding"] for item in data.get("data", [])]
        if len(vectors) != len(arr):
            raise RuntimeError("embedding API returned mismatched number of vectors")
        return vectors
    except Exception as exc:
        logger.exception("OpenAI embeddings failed: %s", exc)
        raise
