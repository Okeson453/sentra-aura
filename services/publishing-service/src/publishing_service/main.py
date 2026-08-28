"""Publishing Service FastAPI service entrypoint.

Multi-platform publishing, scheduling, metadata optimization, post analytics
"""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from publishing_service.config import ServiceConfig

logger = logging.getLogger(__name__)

config: ServiceConfig

# In-memory store (replace with Redis/DB in production)
_store: dict[str, dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global config
    config = ServiceConfig.from_env()
    logging.basicConfig(level=getattr(logging, config.log_level.upper(), logging.INFO))
    logger.info("Publishing Service started: %s v%s", config.service_name, config.version)
    yield
    logger.info("Publishing Service shutting down")


app = FastAPI(
    title="SentraAura Publishing Service",
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


@app.post("/publications")
async def create_publication(request: Request, authorization: str = _require_bearer) -> dict[str, Any]:
    """Create a publication."""
    body = await request.json()
    publication_id = f"pub-{uuid.uuid4().hex[:12]}"
    pub = {
        "publication_id": publication_id,
        "channel_id": body.get("channel_id", ""),
        "title": body.get("title", ""),
        "description": body.get("description", ""),
        "status": "draft",
        "asset_id": body.get("asset_id", ""),
        "thumbnail_asset_id": body.get("thumbnail_asset_id", ""),
        "platforms": body.get("platforms", []),
        "scheduled_at": body.get("scheduled_at"),
        "seo_metadata": body.get("seo_metadata", {}),
        "tags": body.get("tags", []),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    _store[publication_id] = pub
    return pub


@app.get("/publications")
async def list_publications(authorization: str = _require_bearer) -> dict[str, Any]:
    """List publications."""
    return {"status": "ok"}


@app.get("/publications/{publication_id}")
async def get_publication(publication_id: str, authorization: str = _require_bearer) -> dict[str, Any]:
    """Get publication by ID."""
    item = _store.get("get_publication_" + publication_id)
    if not item:
        raise HTTPException(status_code=404, detail="publication_id not found")
    return item


@app.put("/publications/{publication_id}")
async def update_publication(publication_id: str, request: Request, authorization: str = _require_bearer) -> dict[str, Any]:
    """Update publication."""
    body = await request.json()
    item = _store.get(publication_id)
    if not item:
        raise HTTPException(status_code=404, detail="publication_id not found")
    item.update(body)
    item["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return item


@app.delete("/publications/{publication_id}")
async def delete_publication(publication_id: str, authorization: str = _require_bearer) -> None:
    """Delete/archive publication."""
    if publication_id not in _store:
        raise HTTPException(status_code=404, detail="publication_id not found")
    item = _store[publication_id]
    item["status"] = "archived"
    return None


@app.post("/publications/{publication_id}/publish")
async def publish_now(publication_id: str, authorization: str = _require_bearer) -> dict[str, Any]:
    """Publish immediately."""
    pub = _store.get(publication_id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")
    job_id = f"publish-{uuid.uuid4().hex[:12]}"
    job = {
        "job_id": job_id,
        "publication_id": publication_id,
        "status": "queued",
        "platform_results": [],
    }
    _store[job_id] = job
    return job


@app.post("/publications/{publication_id}/schedule")
async def schedule_publication(publication_id: str, request: Request, authorization: str = _require_bearer) -> dict[str, Any]:
    """Schedule publication."""
    body = await request.json()
    pub = _store.get(publication_id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")
    pub["scheduled_at"] = body.get("scheduled_at")
    pub["status"] = "scheduled"
    return pub


@app.post("/publications/{publication_id}/unpublish")
async def unpublish(publication_id: str, authorization: str = _require_bearer) -> dict[str, Any]:
    """Unpublish from platforms."""
    pub = _store.get(publication_id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")
    pub["status"] = "archived"
    return {"status": "unpublished", "publication_id": publication_id}


@app.get("/platforms")
async def list_platforms(authorization: str = _require_bearer) -> list[dict[str, Any]]:
    """List connected publishing platforms."""
    return [
        {
            "platform_id": "youtube",
            "name": "YouTube",
            "status": "connected",
            "capabilities": ["upload", "schedule", "analytics"],
        },
        {
            "platform_id": "tiktok",
            "name": "TikTok",
            "status": "connected",
            "capabilities": ["upload", "schedule"],
        },
    ]



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("publishing_service.main:app", host="0.0.0.0", port=config.port, reload=False)
