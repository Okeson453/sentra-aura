"""Media Renderer FastAPI service entrypoint.

GPU-accelerated video composition, rendering pipeline, format transcoding
"""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from media_renderer.config import ServiceConfig

logger = logging.getLogger(__name__)

config: ServiceConfig

# In-memory store (replace with Redis/DB in production)
_store: dict[str, dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global config
    config = ServiceConfig()
    logging.basicConfig(level=getattr(logging, config.log_level.upper(), logging.INFO))
    logger.info("Media Renderer started: %s v%s", config.service_name, config.version)
    yield
    logger.info("Media Renderer shutting down")


app = FastAPI(
    title="SentraAura Media Renderer",
    version="1.0.0",
    lifespan=lifespan,
)


def _require_bearer(authorization: str | None = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    return authorization[7:]


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"error_code": "VALIDATION_ERROR", "message": str(exc)})



@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check."""
    return {
        "status": "healthy",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "version": config.version,
    }


@app.get("/ready")
async def readiness_check() -> dict[str, Any]:
    """Readiness check."""
    return {
        "status": "healthy",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "version": config.version,
        "checks": {},
    }



@app.post("/render")
async def submit_render_job(request: Request, authorization: str = Depends(_require_bearer)) -> dict[str, Any]:
    """Submit a render job — builds plan via TimelineBuilder when timeline provided."""
    body = await request.json()
    job_id = f"render-{uuid.uuid4().hex[:12]}"
    timeline = body.get("timeline") or []
    plan = {}
    try:
        from media_renderer.service import MediaRendererService
        svc = MediaRendererService()
        plan = svc.build_render_plan({"clips": timeline, "timeline": timeline, "format": body.get("format") or "mp4"})
    except Exception as exc:
        plan = {"error": str(exc), "timeline_clips": len(timeline) if isinstance(timeline, list) else 0}
    job = {
        "job_id": job_id,
        "status": "queued",
        "project_id": body.get("project_id", ""),
        "channel_id": body.get("channel_id", ""),
        "progress_percent": 0,
        "output_url": "",
        "output_format": body.get("format") or "mp4",
        "timeline_clips": len(timeline) if isinstance(timeline, list) else 0,
        "render_plan": plan,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    _store[job_id] = job
    return job


@app.get("/render/jobs/{job_id}")
async def get_render_job(job_id: str, authorization: str = Depends(_require_bearer)) -> dict[str, Any]:
    """Get render job status."""
    item = _store.get("get_render_job_" + job_id)
    if not item:
        raise HTTPException(status_code=404, detail="job_id not found")
    return item


@app.post("/render/jobs/{job_id}/cancel")
async def cancel_render_job(request: Request, authorization: str = Depends(_require_bearer)) -> dict[str, Any]:
    """Cancel a render job."""
    body = await request.json()
    return {"status": "ok", "mock": True}


@app.get("/render/jobs")
async def list_render_jobs(
    channel_id: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    authorization: str = Depends(_require_bearer),
) -> dict[str, Any]:
    """List render jobs."""
    items = [v for v in _store.values() if v.get("status")]
    if channel_id:
        items = [i for i in items if i.get("channel_id") == channel_id]
    if status:
        items = [i for i in items if i.get("status") == status]
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "items": items[start:end],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size,
        },
    }


@app.post("/transcode")
async def submit_transcode_job(request: Request, authorization: str = Depends(_require_bearer)) -> dict[str, Any]:
    """Submit a transcode job."""
    body = await request.json()
    job_id = f"transcode-{uuid.uuid4().hex[:12]}"
    job = {
        "job_id": job_id,
        "status": "queued",
        "source_asset_id": body.get("source_asset_id", ""),
        "target_format": body.get("target_format", "mp4"),
        "progress_percent": 0,
        "output_url": "",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "completed_at": None,
    }
    _store[job_id] = job
    return job


@app.get("/templates")
async def list_templates(authorization: str = Depends(_require_bearer)) -> list[dict[str, Any]]:
    """List available render templates."""
    return [
        {
            "template_id": "standard_1080p",
            "name": "Standard 1080p",
            "description": "Default 1080p render template",
            "compatible_formats": ["mp4", "mov"],
            "default_settings": {"resolution": "1080p", "frame_rate": 30},
        },
    ]



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("media_renderer.main:app", host="0.0.0.0", port=config.port, reload=False)
