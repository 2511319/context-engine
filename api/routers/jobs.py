"""Job status endpoints."""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

from ..services import jobs as jobs_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", summary="List background jobs")
async def list_jobs(project: str | None = Query(default=None, description="Filter by project id")):
    return {"jobs": jobs_service.list_jobs(project)}


@router.get("/{job_id}", summary="Get job details")
async def get_job(job_id: str):
    job = jobs_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@router.get("/{job_id}/log", summary="Read job log")
async def get_job_log(job_id: str):
    content = jobs_service.read_log(job_id)
    if content is None:
        raise HTTPException(status_code=404, detail="log not found")
    return PlainTextResponse(content)
