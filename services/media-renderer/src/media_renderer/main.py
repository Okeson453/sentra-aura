"""Media Renderer FastAPI service entrypoint.

GPU-accelerated video composition, rendering pipeline, format transcoding.
Updated to use database-backed storage and fix job lookup bug.
"""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from sentinel_security.auth import authenticate_request, AuthContext
from fastapi.responses import JSONResponse

from media_renderer.config import ServiceConfig
from media_renderer.service import MediaRendererService
from media_renderer.db.session import get_db, init_db

logger = logging.getLogger(__name__)

config: ServiceConfig

# Initialize database
init_db()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global config
    config = ServiceConfig()
    logging.basicConfig(level=getattr(logging, config.log_level.upper(), logging.INFO))
    logger.info("Media Renderer started: %s v%s", config.service_name, config.version)
    yield
    logger.info("Media Renderer shutting down")



def _verify_bearer(authorization: str | None = Header(None)) -> AuthContext:
    """Verify JWT token using sentinel-security."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization[7:]
    try:
        return authenticate_request(token, jwt_secret=config.jwt_secret)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {e}")



app = FastAPI(
    title="SentraAura Media Renderer",
    version="1.0.0",
    lifespan=lifespan,
)




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
    """Readiness check.
    
    Validates database connectiv
ity and returns actual checks.
    """
    from sqlalchemy import text
    from sqlalchemy.orm import Session
    
    checks = {}
    status = "healthy"
    
    # Check database connectivity
    try:
        db = next(get_db())
        db.execute(text("SELECT 1"))
        db.close()
        checks["database"] = {"status": "ok", "message": "Database connection successful"}
    except Exception as e:
        checks["database"] = {"status": "error", "message": str(e)}
        status = "degraded"
    
    return {
        "status": status,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "version": config.version,
        "checks": checks,
    }


@app.post("/render")
async def submit_render_job(request: Request, authorization: str = Depends(_verify_bearer)) -> dict[str, Any]:
    """Submit a render job — builds plan via TimelineBuilder when timeline provided."""
    body = await request.json()
    job_id = f"render-{uuid.uuid4().hex[:12]}"
    timeline = body.get("timeline") or []
    plan = {}
    try:
        svc = MediaRendererService()
        plan = svc.build_render_plan({"clips": timeline, "timeline": timeline, "format": body.get("format") or "mp4"})
    except Exception as exc:
        plan = {"error": str(exc), "timeline_clips": len(timeline) if isinstance(timeline, list) else 0}
    
    # Create the job in database via service
    from media_renderer.models import RenderRequest
    render_request = RenderRequest(
        project_id=body.get("project_id", ""),
        channel_id=body.get("channel_id", ""),
        tenant_id=body.get("tenant_id", ""),
        output_format=body.get("format") or "mp4",
        resolution=body.get("resolution", "1080p"),
        frame_rate=body.get("frame_rate", 30),
        template_id=body.get("template_id"),
        callback_url=body.get("callback_url"),
    )
    job = await svc.create_render_job(render_request)
    
    # Update with plan
    job["render_plan"] = plan
    job["timeline_clip
s"] = len(timeline) if isinstance(timeline, list) else 0
    
    return job


@app.get("/render/jobs/{job_id}")
async def get_render_job(job_id: str, authorization: str = Depends(_verify_bearer)) -> dict[str, Any]:
    """Get render job status.
    
    Fixed: Now looks up job by job_id directly (not "get_render_job_" + job_id).
    """
    svc = MediaRendererService()
    job = await svc.get_render_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job_id not found")
    return job


@app.post("/render/jobs/{job_id}/cancel")
async def cancel_render_job(request: Request, authorization: str = Depends(_verify_bearer)) -> dict[str, Any]:
    """Cancel a render job."""
    body = await request.json()
    svc = MediaRendererService()
    result = await svc.cancel_job(job_id)
    return {"status": "ok", **result}


@app.get("/render/jobs")
async def list_render_jobs(
    channel_id: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    authorization: str = Depends(_verify_bearer),
) -> dict[str, Any]:
    """List render jobs."""
    svc = MediaRendererService()
    return await svc.list_jobs(channel_id, status, page, page_size)


@app.post("/transcode")
async def submit_transcode_job(request: Request, authorization: str = Depends(_verify_bearer)) -> dict[str, Any]:
    """Submit a transcode job."""
    body = await request.json()
    from media_renderer.models import TranscodeRequest
    transcode_request = TranscodeRequest(
        source_asset_id=body.get("source_asset_id", ""),
        target_format=body.get("target_format", "mp4"),
        target_resolution=body.get("target_resolution", "1080p"),
        target_codec=body.get("target_codec", "h264"),
        bitrate_kbps=body.get("bitrate_kbps"),
    )
    svc = MediaRendererService()
    return await svc.create_transcode_job(transcode_request)


@app.get("/templates")
async def list_templates(authorization: str = Depends(_verify_bearer)) 
-> list[dict[str, Any]]:
    """List available render templates."""
    svc = MediaRendererService()
    return await svc.list_templates()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("media_renderer.main:app", host="0.0.0.0", port=config.port, reload=False)
