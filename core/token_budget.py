from __future__ import annotations

import logging
from typing import Iterable


logger = logging.getLogger(__name__)

try:
    import tiktoken  # type: ignore
except Exception:  # pragma: no cover
    tiktoken = None  # type: ignore


def count_tokens(texts: Iterable[str], model: str = "cl100k_base") -> int:
    """
    Count tokens for a collection of strings using tiktoken if available, otherwise
    approximate by len/4 per string.

    Args:
        texts: Iterable of strings.
        model: Tokenizer model name for tiktoken.

    Returns:
        Total token count.
    """
    if tiktoken is None:
        return sum(max(0, len(t) // 4) for t in texts)

    try:
        enc = tiktoken.get_encoding(model)
        total = 0
        for t in texts:
            total += len(enc.encode(t or ""))
        return total
    except Exception as exc:  # pragma: no cover
        logger.exception("tiktoken failed; falling back to len/4: %s", exc)
        return sum(max(0, len(t) // 4) for t in texts)

