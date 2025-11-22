from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from time import time
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class PolicyConfig:
    project: str
    raw: Dict[str, Any]
    routing_rules: List[Dict[str, Any]]
    sensitive: List[Dict[str, Any]]
    checksum: str
    mtime: float
    ttl_seconds: int
    source: str


class PolicyLoader:
    """Загрузчик policy-конфига с TTL и fallback на engine.yml."""

    def __init__(
        self,
        policy_path: Path,
        default_project: str = "context_engine",
        default_ttl: int = 30,
        engine_path: Path | None = None,
    ) -> None:
        self._policy_path = policy_path
        self._engine_path = engine_path
        self._default_project = default_project
        self._default_ttl = default_ttl
        self._cache: Optional[PolicyConfig] = None

    def get(self) -> PolicyConfig:
        now = time()
        if self._cache and (now - self._cache.mtime) <= self._cache.ttl_seconds:
            return self._cache
        try:
            cfg = self._load()
            self._cache = cfg
            return cfg
        except Exception as exc:  # pragma: no cover
            logger.exception("Failed to load policy config: %s", exc)
            if self._cache:
                return self._cache
            return PolicyConfig(
                project=self._default_project,
                raw={},
                routing_rules=[],
                sensitive=[],
                checksum="",
                mtime=now,
                ttl_seconds=self._default_ttl,
                source=str(self._policy_path),
            )

    def _load(self) -> PolicyConfig:
        engine_raw: Dict[str, Any] = {}
        if self._engine_path and self._engine_path.exists():
            engine_raw = self._load_yaml(self._engine_path)
        fallback_project = (
            str(engine_raw.get("project", self._default_project))
            if isinstance(engine_raw, dict)
            else self._default_project
        )

        if self._policy_path.exists():
            raw = self._load_yaml(self._policy_path)
            source = self._policy_path
        elif isinstance(engine_raw.get("policy"), dict):
            raw = engine_raw.get("policy") or {}
            source = self._engine_path or self._policy_path
        else:
            raw = {}
            source = self._policy_path

        project = str(raw.get("project", fallback_project))
        routing_rules, sensitive = self._validate_policy(raw)
        ttl_seconds = self._extract_ttl(raw, engine_raw)
        checksum = self._checksum(raw)
        mtime = source.stat().st_mtime if source.exists() else time()
        return PolicyConfig(
            project=project,
            raw=raw,
            routing_rules=routing_rules,
            sensitive=sensitive,
            checksum=checksum,
            mtime=mtime,
            ttl_seconds=ttl_seconds,
            source=str(source),
        )

    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        if yaml is None:
            raise RuntimeError("PyYAML is required to load YAML configs. Install 'PyYAML'.")
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError(f"{path.name} must contain a mapping at the root")
        return data

    def _checksum(self, raw: Dict[str, Any]) -> str:
        normalized = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _extract_ttl(self, raw: Dict[str, Any], engine_raw: Dict[str, Any]) -> int:
        ttl = self._default_ttl
        if isinstance(raw.get("observability"), dict):
            ttl = int(raw.get("observability", {}).get("config_ttl_seconds", ttl))
        elif isinstance(engine_raw.get("observability"), dict):
            ttl = int(engine_raw.get("observability", {}).get("config_ttl_seconds", ttl))
        return max(1, ttl)

    def _validate_policy(self, raw: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        routing = raw.get("routing", {}) or {}
        if not isinstance(routing, dict):
            routing = {}
        rules = routing.get("rules", []) or []
        if not isinstance(rules, list):
            rules = []
        rules = [r for r in rules if isinstance(r, dict)]

        sensitive = raw.get("sensitive", []) or []
        if not isinstance(sensitive, list):
            sensitive = []
        sensitive = [s for s in sensitive if isinstance(s, dict)]
        return rules, sensitive
