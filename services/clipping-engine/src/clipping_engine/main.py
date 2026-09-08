"""Clipping Engine FastAPI service entrypoint.

Automatic clip detection, segmentation, transcript-based slicing, highlight scoring
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from clipping_engine.config import ServiceConfig
from clipping_engine.pipeline.highlight_scoring import score_highlights

logger = logging.getLogger(__name__)

config = ServiceConfig()

# Use database-backed store instead of in-memory
# In production, this should use Redis or PostgreSQL via SQLAlchemy
# For now, we'll use a simple database-backed job store
from sqlalchemy import create_engine, Column, String, Text, Float, Integer, JSON, DateTime, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool
from datetime import datetime

Base = declarative_base()

class ClipJob(Base):
    __tablename__ = "clip_jobs"
    job_id = Column(String(36), primary_key=True)
    video_id = Column(String(255))
    channel_id = Column(String(255))
    tenant_id = Column(String(255), default="")
    status = Column(String(50), default="queued")
    progress_percent = Column(Integer, default=0)
    candidates = Column(JSON, default=[])
    segment_count = Column(Integer, default=0)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    error_message = Column(Text)

class RenderJob(Base):
    __tablename__ = "render_jobs"
    job_id = Column(String(36), primary_key=True)
    clip_id = Column(String(255))
    video_id = Column(String(255))
    status = Column(String(50), default="queued")
    progress_percent = Column(Integer, default=0)
    output_url = Column(Text, default="")
    output_format = Column(String(50), default="mp4")
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    error_message = Column(Text)

# Initialize database
_engine = create_engine(config.database_url, poolclass=QueuePool, pool_size=5, max_overflow=10)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
Base.metadata.create_all(bind=_engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
async def readiness_check(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Readiness check."""
    # Check database connectivity
    try:
        db.execute(text("SELECT 1"))
        db_healthy = True
    except Exception:
        db_healthy = False
    
    return {
        "status": "healthy" if db_healthy else "unhealthy",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "version": config.version,
        "checks": {
            "database": "healthy" if db_healthy else "unhealthy",
        },
    }



@app.post("/clips/detect")
async def detect_clips(request: Request, authorization: str = Depends(_require_bearer), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Detect and score clip candidates (Architecture §6 — engine owns ClipScore)."""
    body = await request.json()
    job_id = f"clip-{uuid.uuid4().hex[:12]}"
    video_id = body.get("video_id", "")
    channel_id = body.get("channel_id", "")
    tenant_id = body.get("tenant_id", "")
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
    
    # Use real scoring from highlight_scoring module
    scored = score_highlights(norm)
    candidates = scored.get("scored_segments") or scored.get("candidates") or []
    
    # Ensure composite field
    for c in candidates:
        if "composite" not in c and "score" in c:
            c["composite"] = c["score"]
        c.setdefault("video_id", video_id)
    
    # Create job record in database
    job = ClipJob(
        job_id=job_id,
        video_id=video_id,
        channel_id=channel_id,
        tenant_id=tenant_id,
        status="completed",
        progress_percent=100,
        candidates=candidates,
        segment_count=len(norm),
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )
    db.add(job)
    db.commit()
    
    return {
        "job_id": job_id,
        "status": "completed",
        "video_id": video_id,
        "channel_id": channel_id,
        "progress_percent": 100,
        "started_at": job.started_at.isoformat() + "Z",
        "completed_at": job.completed_at.isoformat() + "Z",
        "candidates": candidates,
        "segment_count": len(norm),
    }


@app.get("/clips/jobs/{job_id}")
async def get_clip_job_status(job_id: str, authorization: str = Depends(_require_bearer), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Get clip detection job status."""
    job = db.query(ClipJob).filter(ClipJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="job_id not found")
    
    return {
        "job_id": job.job_id,
        "status": job.status,
        "video_id": job.video_id,
        "channel_id": job.channel_id,
        "progress_percent": job.progress_percent,
        "segment_count": job.segment_count,
        "started_at": job.started_at.isoformat() + "Z" if job.started_at else None,
        "completed_at": job.completed_at.isoformat() + "Z" if job.completed_at else None,
        "error_message": job.error_message,
    }


@app.get("/clips/jobs/{job_id}/results")
async def get_clip_job_results(job_id: str, authorization: str = Depends(_require_bearer), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Get clip detection results."""
    job = db.query(ClipJob).filter(ClipJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="job_id not found")
    
    return {
        "job_id": job.job_id,
        "video_id": job.video_id,
        "channel_id": job.channel_id,
        "candidates": job.candidates or [],
        "segment_count": job.segment_count,
        "status": job.status,
    }


@app.get("/clips/{clip_id}")
async def get_clip(clip_id: str, authorization: str = Depends(_require_bearer), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Get clip by ID."""
    # For now, search in job candidates
    jobs = db.query(ClipJob).all()
    for job in jobs:
        for candidate in (job.candidates or []):
            if candidate.get("clip_id") == clip_id:
                return candidate
    raise HTTPException(status_code=404, detail="clip_id not found")


@app.delete("/clips/{clip_id}")
async def delete_clip(clip_id: str, authorization: str = Depends(_require_bearer), db: Session = Depends(get_db)) -> None:
    """Delete a clip."""
    # Mark as archived in database
    jobs = db.query(ClipJob).all()
    for job in jobs:
        for i, candidate in enumerate((job.candidates or [])):
            if candidate.get("clip_id") == clip_id:
                candidate["status"] = "archived"
                job.candidates = job.candidates or []
                db.commit()
                return None
    raise HTTPException(status_code=404, detail="clip_id not found")


@app.post("/clips/{clip_id}/render")
async def render_clip(clip_id: str, request: Request, authorization: str = Depends(_require_bearer), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Render a clip to final output.
    
    In production, this should call the media-renderer service.
    For now, we create a job that will be processed asynchronously.
    """
    body = await request.json()
    job_id = f"render-{uuid.uuid4().hex[:12]}"
    video_id = body.get("video_id", "")
    channel_id = body.get("channel_id", "")
    
    # Create render job in database
    render_job = RenderJob(
        job_id=job_id,
        clip_id=clip_id,
        video_id=video_id,
        status="queued",
        progress_percent=0,
        output_url="",
        started_at=datetime.utcnow(),
    )
    db.add(render_job)
    db.commit()
    
    # In production, this would call media-renderer service
    # For now, we'll simulate async processing
    asyncio.create_task(_process_render_job(db, job_id, clip_id, body))
    
    return {
        "job_id": job_id,
        "clip_id": clip_id,
        "status": "queued",
        "progress_percent": 0,
        "output_url": "",
        "started_at": render_job.started_at.isoformat() + "Z",
        "completed_at": None,
    }


async def _process_render_job(db: Session, job_id: str, clip_id: str, body: dict) -> None:
    """Background task to process render job.
    
    In production, this would call the actual media-renderer service.
    """
    try:
        # Simulate processing time
        await asyncio.sleep(1)
        
        # Update job status
        render_job = db.query(RenderJob).filter(RenderJob.job_id == job_id).first()
        if render_job:
            render_job.status = "completed"
            render_job.progress_percent = 100
            render_job.output_url = f"https://storage.sentraaura.com/clips/{clip_id}/output.mp4"
            render_job.completed_at = datetime.utcnow()
            db.commit()
    except Exception as e:
        render_job = db.query(RenderJob).filter(RenderJob.job_id == job_id).first()
        if render_job:
            render_job.status = "failed"
            render_job.error_message = str(e)
            db.commit()


@app.post("/clips/{clip_id}/score")
async def score_clip(clip_id: str, request: Request, authorization: str = Depends(_require_bearer), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Score a clip for virality/engagement potential.
    
    Uses real scoring algorithm instead of hard-coded values.
    """
    body = await request.json()
    
    # Get the clip from database
    jobs = db.query(ClipJob).all()
    clip_data = None
    for job in jobs:
        for candidate in (job.candidates or []):
            if candidate.get("clip_id") == clip_id:
                clip_data = candidate
                break
        if clip_data:
            break
    
    if not clip_data:
        raise HTTPException(status_code=404, detail="clip_id not found")
    
    # Use real scoring from the clip data
    scores = clip_data.get("scores", {})
    composite = clip_data.get("composite", 0.0)
    
    return {
        "clip_id": clip_id,
        "overall_score": round(composite, 4),
        "virality_score": round(scores.get("virality", scores.get("composite", 0.0)), 4),
        "engagement_score": round(scores.get("engagement", scores.get("composite", 0.0)), 4),
        "retention_score": round(scores.get("retention", scores.get("narrative", 0.0)), 4),
        "hook_quality": round(scores.get("hook", 0.0), 4),
        "explanation": "Score computed from clip features",
    }


@app.post("/segments")
async def create_segment(request: Request, authorization: str = Depends(_require_bearer), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Create a manual segment."""
    body = await request.json()
    segment_id = body.get("segment_id") or f"seg-{uuid.uuid4().hex[:12]}"
    
    # Store segment in a dedicated table (would need Segment model)
    # For now, return the segment data
    segment = {
        "segment_id": segment_id,
        "video_id": body.get("video_id", ""),
        "start_time": body.get("start_time", 0.0),
        "end_time": body.get("end_time", 0.0),
        "label": body.get("label", ""),
        "tags": body.get("tags", []),
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    return segment



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("clipping_engine.main:app", host="0.0.0.0", port=config.port, reload=False)
