"""Admin-facing services: health, jobs, plans, config."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from api.adapters import mcp
from api.deps import get_settings
from api.services import jobs as jobs_service
from api.services import plans as plans_service
from core.config.policy import PolicyLoader
from core.config_loader import ConfigLoader, EngineConfig
from core.dal import GraphClient, PgClient


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class _ComponentStatus:
    name: str
    status: str
    message: str = ""
    checked_at: str = _now_iso()

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "checked_at": self.checked_at,
        }


class AdminService:
    """Aggregate system state for Admin UI endpoints."""

    def __init__(self) -> None:
        settings = get_settings()
        self._settings = settings
        self._pg = PgClient(settings.pg_dsn_ro)
        self._engine_path = settings.project_root / "config" / "engine.yml"
        self._policy_path = settings.project_root / "config" / "policy.yml"
        self._config_loader = ConfigLoader(self._engine_path)
        self._policy_loader = PolicyLoader(
            policy_path=self._policy_path, engine_path=self._engine_path, default_project="context_engine"
        )

    # --------------------------------------------- health
    async def health(self, project: Optional[str] = None, include_mcp: bool = True) -> Dict[str, Any]:
        checked_at = _now_iso()
        components = [self._pg_health(checked_at), self._neo4j_health(checked_at)]
        if include_mcp:
            components.append(await self._mcp_health(checked_at))
        components.append(_ComponentStatus(name="backend_api", status="ok", checked_at=checked_at).as_dict())
        recent = self._recent_down_events(project)
        return {"project": project or self._default_project(), "components": components, "recent_down_events": recent}

    def _pg_health(self, checked_at: str) -> Dict[str, Any]:
        try:
            with self._pg.connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            return _ComponentStatus(name="postgres", status="ok", checked_at=checked_at).as_dict()
        except Exception as exc:  # pragma: no cover - diagnostics only
            return _ComponentStatus(name="postgres", status="down", message=str(exc), checked_at=checked_at).as_dict()

    def _neo4j_health(self, checked_at: str) -> Dict[str, Any]:
        uri = self._settings.neo4j_uri_ro
        user = self._settings.neo4j_user_ro
        password = self._settings.neo4j_pass_ro
        if not (uri and user and password):
            return _ComponentStatus(
                name="neo4j", status="down", message="neo4j ro credentials are not configured", checked_at=checked_at
            ).as_dict()
        try:
            client = GraphClient(uri, user, password)
            with client.session() as session:
                session.run("RETURN 1 AS ok").single()
            return _ComponentStatus(name="neo4j", status="ok", checked_at=checked_at).as_dict()
        except Exception as exc:  # pragma: no cover - diagnostics only
            return _ComponentStatus(name="neo4j", status="down", message=str(exc), checked_at=checked_at).as_dict()

    async def _mcp_health(self, checked_at: str) -> Dict[str, Any]:
        try:
            client = mcp.get_client()
        except Exception as exc:  # pragma: no cover - diagnostics only
            return _ComponentStatus(name="mcp_get_context", status="down", message=str(exc), checked_at=checked_at).as_dict()

        try:
            tools = await client.list_tools()
            status = "ok" if tools else "degraded"
            message = "" if tools else "no tools returned"
            return _ComponentStatus(
                name="mcp_get_context", status=status, message=message, checked_at=checked_at
            ).as_dict()
        except Exception as exc:  # pragma: no cover - diagnostics only
            return _ComponentStatus(name="mcp_get_context", status="down", message=str(exc), checked_at=checked_at).as_dict()

    def _recent_down_events(self, project: Optional[str]) -> List[Dict[str, Any]]:
        records = plans_service.fetch_recent_plans(limit=50, project=project)
        events: List[Dict[str, Any]] = []
        for rec in records:
            if rec.status.lower() != "down":
                continue
            detail = rec.detail or {}
            component = detail.get("component") or rec.route or "unknown"
            error_code = detail.get("error_code") or detail.get("status") or ""
            events.append(
                {
                    "component": component,
                    "error_code": error_code,
                    "plan_id": rec.plan_id,
                    "ts": rec.ts.isoformat(),
                }
            )
        return events

    # --------------------------------------------- jobs
    def list_jobs(
        self,
        project: Optional[str],
        job_type: Optional[str],
        status: Optional[str],
        ts_from: Optional[str],
        ts_to: Optional[str],
        limit: int,
        offset: int,
    ) -> tuple[List[Dict[str, Any]], int]:
        jobs = jobs_service.list_jobs(project)
        filtered: List[Dict[str, Any]] = []
        for job in jobs:
            if job_type and not (job.get("name") or "").startswith(job_type):
                continue
            if status and str(job.get("status", "")).lower() != status.lower():
                continue
            if ts_from and not self._is_after(job.get("started_at"), ts_from):
                continue
            if ts_to and not self._is_before(job.get("started_at"), ts_to):
                continue
            filtered.append(job)
        total = len(filtered)
        return filtered[offset : offset + limit], total

    def _is_after(self, value: Optional[str], bound: str) -> bool:
        try:
            return value is not None and datetime.fromisoformat(value) >= datetime.fromisoformat(bound)
        except Exception:  # pragma: no cover - defensive parsing
            return True

    def _is_before(self, value: Optional[str], bound: str) -> bool:
        try:
            return value is not None and datetime.fromisoformat(value) <= datetime.fromisoformat(bound)
        except Exception:  # pragma: no cover - defensive parsing
            return True

    # --------------------------------------------- plans
    def plans(self, project: Optional[str], status: Optional[str], limit: int, offset: int) -> List[Dict[str, Any]]:
        records = plans_service.fetch_recent_plans(limit=limit, project=project, offset=offset)
        items: List[Dict[str, Any]] = []
        for rec in records:
            if status and rec.status.lower() != status.lower():
                continue
            items.append(self._serialize_plan(rec, include_detail=False))
        return items

    def plan_detail(self, plan_id: str) -> Optional[Dict[str, Any]]:
        rec = plans_service.fetch_plan(plan_id)
        if not rec:
            return None
        return self._serialize_plan(rec, include_detail=True)

    def _serialize_plan(self, record: plans_service.PlanRecordDTO, include_detail: bool) -> Dict[str, Any]:
        payload = {
            "plan_id": record.plan_id,
            "ts": record.ts.isoformat(),
            "project": record.project,
            "module": record.module,
            "status": record.status,
            "route": record.route,
            "latency_ms": record.latency_ms,
            "source_latencies": record.source_latencies,
            "result_sizes": record.result_sizes,
            "params": record.params,
            "token_budget": record.token_budget,
        }
        if include_detail:
            payload["detail"] = record.detail
        return payload

    # --------------------------------------------- config
    def config_snapshot(self, project: Optional[str]) -> Dict[str, Any]:
        engine = self._config_loader.get()
        policy = self._policy_loader.get()
        return {
            "project": project or engine.project,
            "engine": self._engine_payload(engine),
            "policy": self._policy_payload(policy),
        }

    def _engine_payload(self, cfg: EngineConfig) -> Dict[str, Any]:
        file_text = self._engine_path.read_text(encoding="utf-8") if self._engine_path.exists() else ""
        return {
            "project": cfg.project,
            "checksum": cfg.checksum,
            "ttl_seconds": cfg.ttl_seconds,
            "source": str(self._engine_path),
            "raw": cfg.raw,
            "file_text": file_text,
        }

    def _policy_payload(self, policy_cfg) -> Dict[str, Any]:
        policy_text = self._policy_path.read_text(encoding="utf-8") if self._policy_path.exists() else ""
        return {
            "project": policy_cfg.project,
            "checksum": policy_cfg.checksum,
            "ttl_seconds": policy_cfg.ttl_seconds,
            "source": policy_cfg.source,
            "raw": policy_cfg.raw,
            "file_text": policy_text,
        }

    def default_project(self) -> str:
        return self._default_project()

    def _default_project(self) -> str:
        try:
            return self._config_loader.get().project
        except Exception:
            return "context_engine"


_service: AdminService | None = None


def get_admin_service() -> AdminService:
    global _service
    if _service is None:
        _service = AdminService()
    return _service
