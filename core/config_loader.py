from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from time import time
from typing import Any, Dict, Optional

try:
    import yaml
except Exception as exc:  # pragma: no cover
    yaml = None  # type: ignore


logger = logging.getLogger(__name__)


@dataclass
class EngineConfig:
    """Engine configuration model loaded from engine.yml.

    Attributes:
        project: Project identifier string.
        raw: Raw parsed YAML dictionary for inclusion in responses.
        checksum: SHA256 checksum of the normalized content.
        mtime: Last modification time of the config file (float epoch seconds).
        ttl_seconds: TTL for hot reloads.
    """

    project: str
    raw: Dict[str, Any]
    checksum: str
    mtime: float
    ttl_seconds: int


class ConfigLoader:
    """Loads and hot-reloads `engine.yml` with TTL.

    Usage:
        loader = ConfigLoader(Path("config/engine.yml"), default_ttl=30)
        cfg = loader.get()
    """

    def __init__(self, path: Path, default_ttl: int = 30) -> None:
        self._path = path
        self._default_ttl = default_ttl
        self._cache: Optional[EngineConfig] = None

    def _compute_checksum(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _normalize_for_checksum(self, data: Dict[str, Any]) -> str:
        return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def _load_yaml(self) -> Dict[str, Any]:
        if yaml is None:
            raise RuntimeError("PyYAML is required to load engine.yml. Please install 'PyYAML'.")
        text = self._path.read_text(encoding="utf-8")
        data = yaml.safe_load(text) or {}
        if not isinstance(data, dict):
            raise ValueError("engine.yml must define a mapping at the root")
        return data

    def _extract_ttl(self, raw: Dict[str, Any]) -> int:
        ttl = (
            int(
                raw.get("observability", {}).get("config_ttl_seconds", self._default_ttl)  # type: ignore[arg-type]
            )
            if isinstance(raw.get("observability"), dict)
            else self._default_ttl
        )
        return max(1, ttl)

    def _build(self, raw: Dict[str, Any]) -> EngineConfig:
        project = str(raw.get("project", "context_engine"))
        ttl_seconds = self._extract_ttl(raw)
        normalized = self._normalize_for_checksum(raw)
        checksum = self._compute_checksum(normalized)
        mtime = self._path.stat().st_mtime
        return EngineConfig(project=project, raw=raw, checksum=checksum, mtime=mtime, ttl_seconds=ttl_seconds)

    def get(self) -> EngineConfig:
        """Get config with TTL-based hot reload.

        Returns:
            EngineConfig: Cached or freshly loaded configuration.
        """
        now = time()
        if self._cache is None:
            raw = self._load_yaml()
            self._cache = self._build(raw)
            return self._cache

        # Fast path: within TTL
        if (now - self._cache.mtime) <= self._cache.ttl_seconds:
            return self._cache

        # Check if file actually changed (mtime)
        try:
            current_mtime = self._path.stat().st_mtime
        except FileNotFoundError as exc:
            logger.error("engine.yml missing: %s", exc)
            # Fail-closed: keep last valid
            return self._cache

        if current_mtime <= self._cache.mtime:
            # No change
            self._cache.mtime = current_mtime
            return self._cache

        # Attempt to load new config; on error, keep last valid (fail-closed)
        try:
            raw = self._load_yaml()
            new_cfg = self._build(raw)
            self._cache = new_cfg
        except Exception as exc:  # pragma: no cover
            logger.exception("Invalid engine.yml; keeping last valid: %s", exc)
            # keep old cache
        return self._cache

