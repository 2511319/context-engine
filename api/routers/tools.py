"""Quick tools endpoints."""

from fastapi import APIRouter

from ..adapters import mcp
from ..models.tools import (
    ExplainPlanRequest,
    GetContextRequest,
    GraphifyRequest,
    IndexRepoRequest,
    IngestRequest,
    PinRequest,
    SearchRawRequest,
)

router = APIRouter(prefix="/tools", tags=["tools"])


@router.post("/ingest")
async def ingest(req: IngestRequest):
    client = mcp.get_client()
    return await client.call_tool("ingest", req.model_dump())


@router.post("/graphify")
async def graphify(req: GraphifyRequest):
    client = mcp.get_client()
    return await client.call_tool("graphify", req.model_dump())


@router.post("/index_repo")
async def index_repo(req: IndexRepoRequest):
    client = mcp.get_client()
    return await client.call_tool("index_repo", req.model_dump())


@router.post("/search_raw")
async def search_raw(req: SearchRawRequest):
    client = mcp.get_client()
    return await client.call_tool("search_raw", req.model_dump())


@router.post("/pin")
async def pin(req: PinRequest):
    client = mcp.get_client()
    return await client.call_tool("pin", req.model_dump())


@router.post("/forget")
async def forget(req: PinRequest):
    client = mcp.get_client()
    return await client.call_tool("forget", req.model_dump())


@router.post("/explain_plan")
async def explain_plan(req: ExplainPlanRequest):
    client = mcp.get_client()
    return await client.call_tool("explain_plan", req.model_dump())


@router.post("/get_context")
async def get_context(req: GetContextRequest):
    client = mcp.get_client()
    payload = {k: v for k, v in req.model_dump().items() if v is not None}
    return await client.call_tool("get_context", payload)
