"""Config viewer endpoint."""

from fastapi import APIRouter

from ..services.config import get_config_service

router = APIRouter(prefix="/config", tags=["config"])


@router.get("", summary="Active engine configuration")
async def get_config():
    service = get_config_service()
    return service.current()
