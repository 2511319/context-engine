"""Index health endpoints."""

from fastapi import APIRouter, Query

from ..services import health as health_service

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/index", summary="Index health metrics")
async def index_health(project: str = Query("context_engine")):
    return health_service.fetch_index_metrics(project=project)
