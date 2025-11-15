"""Schema browser endpoints."""

from fastapi import APIRouter, HTTPException

from ..services import schema as schema_service

router = APIRouter(prefix="/db", tags=["schema"])


@router.get("/schema", summary="List tables")
async def list_tables():
    return {"tables": schema_service.list_tables()}


@router.get("/table/{table_name}", summary="Describe table")
async def describe_table(table_name: str):
    tables = schema_service.list_tables()
    if table_name not in tables:
        raise HTTPException(status_code=404, detail="Table not found")
    return schema_service.describe_table(table_name)
