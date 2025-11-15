"""Endpoints for plan activity."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import anyio
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from sse_starlette import EventSourceResponse

from ..services import plans as plans_service

router = APIRouter(prefix="/plans", tags=["plans"])


def _serialize_plan(record: plans_service.PlanRecordDTO) -> dict[str, Any]:
    return {
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
        "detail": record.detail,
    }


@router.get("", summary="List recent plans")
async def list_plans(
    limit: int = Query(default=25, ge=1, le=200),
    project: str | None = Query(default=None, description="Filter by project id"),
) -> list[dict]:
    """Return recent plan log entries."""
    records = plans_service.fetch_recent_plans(limit=limit, project=project)
    return [_serialize_plan(rec) for rec in records]


@router.get("/export", summary="Download recent plans as NDJSON")
async def export_plans(
    limit: int = Query(default=200, ge=1, le=1000),
    project: str | None = Query(default=None, description="Filter by project id"),
):
    records = plans_service.fetch_recent_plans(limit=limit, project=project)

    def _generator():
        for record in records:
            yield json.dumps(_serialize_plan(record), ensure_ascii=False) + "\n"

    headers = {"Content-Disposition": 'attachment; filename="plan-log.ndjson"'}
    return StreamingResponse(_generator(), media_type="application/x-ndjson", headers=headers)


@router.get("/{plan_id}", summary="Get plan details")
async def get_plan(plan_id: str):
    record = plans_service.fetch_plan(plan_id)
    if not record:
        raise HTTPException(status_code=404, detail="plan not found")
    return _serialize_plan(record)


@router.get("/stream", summary="Stream latest plans via SSE")
async def stream_plans(project: str | None = Query(default=None, description="Filter by project id")):
    async def event_generator():
        last_id: str | None = None
        while True:
            records = await anyio.to_thread.run_sync(plans_service.fetch_recent_plans, 1, project)
            if records:
                rec = records[0]
                if rec.plan_id != last_id:
                    last_id = rec.plan_id
                    yield {"event": "plan", "data": json.dumps(_serialize_plan(rec))}
            await asyncio.sleep(2)

    return EventSourceResponse(event_generator())
