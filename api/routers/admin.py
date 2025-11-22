"""Admin UI endpoints (/api/admin/*)."""

from fastapi import APIRouter, HTTPException, Query

from ..services.admin import get_admin_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/health", summary="Aggregated component health")
async def admin_health(
    project: str | None = Query(default=None, description="Project id"),
    include_mcp: bool = Query(default=True, description="Include MCP health check"),
):
    service = get_admin_service()
    return await service.health(project, include_mcp=include_mcp)


@router.get("/jobs", summary="List ingest/graphify jobs")
async def admin_jobs(
    project: str | None = Query(default=None, description="Filter by project id"),
    job_type: str | None = Query(default=None, alias="type", description="Filter by job name prefix"),
    status: str | None = Query(default=None, description="Filter by status (queued/running/success/failed)"),
    from_ts: str | None = Query(default=None, alias="from", description="ISO timestamp lower bound"),
    to_ts: str | None = Query(default=None, alias="to", description="ISO timestamp upper bound"),
    limit: int = Query(default=200, ge=1, le=1000, description="Limit number of jobs"),
    offset: int = Query(default=0, ge=0, description="Offset for jobs"),
):
    service = get_admin_service()
    jobs, total = service.list_jobs(project, job_type, status, from_ts, to_ts, limit, offset)
    return {
        "project": project or service.default_project(),
        "jobs": jobs,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/plans", summary="List recent plans")
async def admin_plans(
    project: str | None = Query(default=None, description="Filter by project id"),
    status: str | None = Query(default=None, description="Filter by status (ok/down/queued)"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    service = get_admin_service()
    plans = service.plans(project, status, limit, offset)
    total = len(plans) + offset  # lightweight; no count query
    return {"project": project or service.default_project(), "plans": plans, "limit": limit, "offset": offset, "total": total}


@router.get("/plans/{plan_id}", summary="Get plan detail")
async def admin_plan(plan_id: str):
    service = get_admin_service()
    plan = service.plan_detail(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="plan not found")
    return plan


@router.get("/config", summary="Engine and policy configs (read-only)")
async def admin_config(project: str | None = Query(default=None, description="Project id override")):
    service = get_admin_service()
    return service.config_snapshot(project)
