"""Configuration helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from core.config_loader import ConfigLoader

from ..deps import get_settings


class ConfigService:
    def __init__(self) -> None:
        settings = get_settings()
        self._config_path = settings.project_root / "config" / "engine.yml"
        self._loader = ConfigLoader(self._config_path)

    def current(self) -> Dict[str, Any]:
        cfg = self._loader.get()
        file_text = self._config_path.read_text(encoding="utf-8")
        return {
            "project": cfg.project,
            "checksum": cfg.checksum,
            "ttl_seconds": cfg.ttl_seconds,
            "raw": cfg.raw,
            "file_text": file_text,
        }


_service: ConfigService | None = None


def get_config_service() -> ConfigService:
    global _service
    if _service is None:
        _service = ConfigService()
    return _service
