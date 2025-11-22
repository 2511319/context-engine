"""FastAPI entrypoint for the Context Engine UI backend."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .adapters import mcp
from .deps import get_settings
from .routers import config as config_router
from .routers import admin, graph, health, jobs as jobs_router, plans, root, schema, tools


@asynccontextmanager
async def lifespan(app: FastAPI):
    await mcp.startup_client()
    try:
        yield
    finally:
        await mcp.shutdown_client()


app = FastAPI(title="Context Engine UI", version="0.1.0", lifespan=lifespan)

# Basic CORS policy for local development; adjust if exposing externally.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:8900"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(root.router)
app.include_router(admin.router)
app.include_router(plans.router)
app.include_router(graph.router)
app.include_router(health.router)
app.include_router(schema.router)
app.include_router(config_router.router)
app.include_router(tools.router)
app.include_router(jobs_router.router)

settings = get_settings()
static_dir = settings.project_root / "api" / "static"
if static_dir.exists():
    app.mount("/ui", StaticFiles(directory=static_dir, html=True), name="ui")


@app.get("/healthz", tags=["system"])
async def healthcheck() -> dict[str, str]:
    """Return a simple heartbeat for monitoring."""
    return {"status": "ok"}
