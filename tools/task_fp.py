from __future__ import annotations

import hashlib
import logging
import unicodedata


logger = logging.getLogger(__name__)


def compute_task_fp(text: str) -> str:
    """
    Compute stable task fingerprint for dp_feedback.task_fp.

    Normalization pipeline:
      1) Unicode NFKC
      2) Collapse all whitespace to single spaces
      3) Lowercase
      4) sha256 hex digest

    Args:
        text: Raw task text.

    Returns:
        Hex-encoded sha256 fingerprint.

    Raises:
        ValueError: If input is empty or only whitespace.
    """
    try:
        if text is None:
            raise ValueError("text is None")
        # Step 1: NFKC normalization
        normalized = unicodedata.normalize("NFKC", text)
        # Step 2: collapse whitespace (including newlines/tabs)
        collapsed = " ".join(normalized.split())
        if not collapsed:
            raise ValueError("text is empty after normalization")
        # Step 3: lowercase
        lowered = collapsed.lower()
        # Step 4: sha256
        fp = hashlib.sha256(lowered.encode("utf-8")).hexdigest()
        return fp
    except Exception as exc:
        logger.exception("Failed to compute task_fp: %s", exc)
        raise

