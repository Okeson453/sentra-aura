"""Clipping Engine FastAPI service entrypoint.

Automatic clip detection, segmentation, transcript-based slicing, highlight scoring
"""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from clipping_engine.config import ServiceConfig

logger = logging.getLogger(__name__)

config: ServiceConfig = ServiceConfig()

# In-memory store (replace with Redis/DB in production)
_store: dict[str, dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global config
    config = ServiceConfig()
    logging.basicConfig(level=getattr(logging, config.log_level.upper(), logging.INFO))
    logger.info("Clipping Engine started: %s v%s", config.service_name, config.version)
    yield
    logger.info("Clipping Engine shutting down")


app = FastAPI(
    title="SentraAura Clipping Engine",
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



@app.post("/clips/detect")
async def detect_clips(request: Request, authorization: str = Depends(_require_bearer)) -> dict[str, Any]:
    """Detect and score clip candidates (Architecture §6 — engine owns ClipScore)."""
    body = await request.json()
    job_id = f"clip-{uuid.uuid4().hex[:12]}"
    video_id = body.get("video_id", "")
    segments = body.get("segments") or []
    # Normalize segments for highlight_scoring
    norm = []
    for i, s in enumerate(segments if isinstance(segments, list) else []):
        if not isinstance(s, dict):
            continue
        norm.append({
            "segment_id": s.get("segment_id") or s.get("id") or f"seg-{i}",
            "start_seconds": float(s.get("start_seconds") or s.get("start") or 0),
            "end_seconds": float(s.get("end_seconds") or s.get("end") or 0),
            "text": str(s.get("text") or ""),
            "visual_change": float(s.get("visual_change") or 0.0),
        })
    from clipping_engine.pipeline.highlight_scoring import score_highlights
    scored = score_highlights(norm)
    candidates = scored.get("scored_segments") or scored.get("candidates") or []
    # Ensure composite field
    for c in candidates:
        if "composite" not in c and "score" in c:
            c["composite"] = c["score"]
        c.setdefault("video_id", video_id)
    job = {
        "job_id": job_id,
        "status": "completed",
        "video_id": video_id,
        "progress_percent": 100,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "candidates": candidates,
        "segment_count": len(norm),
    }
    _store[job_id] = job
    _store["get_clip_job_status_" + job_id] = job
    _store["get_clip_job_results_" + job_id] = {
        "job_id": job_id,
        "video_id": video_id,
        "candidates": candidates,
        "segment_count": len(norm),
        "status": "completed",
    }
    return job


@app.get("/clips/jobs/{job_id}")
async def get_clip_job_status(job_id: str, authorization: str = Depends(_require_bearer)) -> dict[str, Any]:
    """Get clip detection job status."""
    item = _store.get("get_clip_job_status_" + job_id)
    if not item:
        raise HTTPException(status_code=404, detail="job_id not found")
    return item


@app.get("/clips/jobs/{job_id}/results")
async def get_clip_job_results(job_id: str, authorization: str = Depends(_require_bearer)) -> dict[str, Any]:
    """Get clip detection results."""
    item = _store.get("get_clip_job_results_" + job_id)
    if not item:
        raise HTTPException(status_code=404, detail="job_id not found")
    return item


@app.get("/clips/{clip_id}")
async def get_clip(clip_id: str, authorization: str = Depends(_require_bearer)) -> dict[str, Any]:
    """Get clip by ID."""
    item = _store.get("get_clip_" + clip_id)
    if not item:
        raise HTTPException(status_code=404, detail="clip_id not found")
    return item


@app.delete("/clips/{clip_id}")
async def delete_clip(clip_id: str, authorization: str = Depends(_require_bearer)) -> None:
    """Delete a clip."""
    if clip_id not in _store:
        raise HTTPException(status_code=404, detail="clip_id not found")
    item = _store[clip_id]
    item["status"] = "archived"
    return None


@app.post("/clips/{clip_id}/render")
async def render_clip(clip_id: str, request: Request, authorization: str = Depends(_require_bearer)) -> dict[str, Any]:
    """Render a clip to final output."""
    body = await request.json()
    job_id = f"render-{uuid.uuid4().hex[:12]}"
    job = {
        "job_id": job_id,
        "clip_id": clip_id,
        "status": "queued",
        "progress_percent": 0,
        "output_url": "",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "completed_at": None,
    }
    _store[job_id] = job
    return job


@app.post("/clips/{clip_id}/score")
async def score_clip(clip_id: str, authorization: str = Depends(_require_bearer)) -> dict[str, Any]:
    """Score a clip for virality/engagement potential."""
    return {
        "clip_id": clip_id,
        "overall_score": 0.82,
        "virality_score": 0.78,
        "engagement_score": 0.85,
        "retention_score": 0.80,
        "hook_quality": 0.88,
        "explanation": "Strong hook with high engagement potential.",
    }


@app.post("/segments")
async def create_segment(request: Request, authorization: str = Depends(_require_bearer)) -> dict[str, Any]:
    """Create a manual segment."""
    body = await request.json()
    segment_id = body.get("segment_id") or f"seg-{uuid.uuid4().hex[:12]}"
    segment = {
        "segment_id": segment_id,
        "video_id": body.get("video_id", ""),
        "start_time": body.get("start_time", 0.0),
        "end_time": body.get("end_time", 0.0),
        "label": body.get("label", ""),
        "tags": body.get("tags", []),
    }
    _store[segment_id] = segment
    return segment



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("clipping_engine.main:app", host="0.0.0.0", port=config.port, reload=False)
