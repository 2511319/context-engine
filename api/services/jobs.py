"""Filesystem-based view over MCP background jobs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..deps import get_settings


def _jobs_dir() -> Path:
    settings = get_settings()
    directory = settings.project_root / "logs" / "jobs"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def list_jobs(project: str | None = None) -> List[Dict[str, Any]]:
    directory = _jobs_dir()
    jobs: List[Dict[str, Any]] = []
    for path in sorted(directory.glob("*.json"), reverse=True):
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
            if project and job.get("project") != project:
                continue
            jobs.append(job)
        except Exception:  # pragma: no cover
            continue
    return jobs


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    path = _jobs_dir() / f"{job_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # pragma: no cover
        return None


def read_log(job_id: str) -> Optional[str]:
    path = _jobs_dir() / f"{job_id}.log"
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:  # pragma: no cover
        return None
