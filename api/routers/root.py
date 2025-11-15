"""Basic router with placeholder endpoints."""

from fastapi import APIRouter

router = APIRouter(tags=["root"])


@router.get("/", summary="Root endpoint")
async def read_root() -> dict[str, str]:
    """Return a friendly greeting for manual testing."""
    return {"message": "Context Engine UI backend is up"}
