"""Graph endpoints."""

from fastapi import APIRouter, Query

from ..services import graph as graph_service

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("", summary="Fetch module subgraph")
async def get_graph(
    project: str = Query("context_engine"),
    module: str = Query(...),
    depth: int = Query(3, ge=1, le=5),
    relations: list[str] | None = Query(None),
):
    return graph_service.fetch_subgraph(project=project, module=module, depth=depth, relations=relations)


@router.get("/stats", summary="Graph statistics")
async def get_graph_stats(project: str = Query("context_engine")):
    return graph_service.fetch_stats(project=project)
