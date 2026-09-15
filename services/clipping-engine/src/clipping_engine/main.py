"""Clipping Engine FastAPI service entrypoint.

Automatic clip detection, segmentation, transcript-based slicing, highlight scoring
"""
from __future__ import annotations

import asyncio
import httpx
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sentinel_security.auth import AuthContext, authenticate_request
from sqlalchemy import text
from sqlalchemy.orm import Session

from clipping_engine.config import ServiceConfig
from clipping_engine.persistence import ClipJob, RenderJob, Segment, get_db
from clipping_engine.pipeline.asr_transcription import transcribe_audio
from clipping_engine.pipeline.audio_extraction import extract_audio
from clipping_engine.pipeline.highlight_scoring import score_highlights
from clipping_engine.pipeline.scene_detection import detect_scenes
from clipping_engine.pipeline.semantic_segmentation import segment_semantically
from clipping_engine.pipeline.shot_detection import detect_shots
from clipping_engine.pipeline.speaker_diarization import diarize_speakers

logger = logging.getLogger(__name__)

config = ServiceConfig()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global config
    config = ServiceConfig()
    logging.basicConfig(level=getattr(logging, config.log_level.upper(), logging.INFO))
    logger.info("Clipping Engine started: %s v%s", config.service_name, config.version)
    yield
    logger.info("Clipping Engine shutting down")


def _verify_bearer(authorization: str | None = Header(None)) -> AuthContext:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization[7:]
    try:
        return authenticate_request(token, jwt_secret=config.jwt_secret)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {e}")


app = FastAPI(
    title="SentraAura Clipping Engine",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"error_code": "VALIDATION_ERROR", "message": str(exc)})


@app.get("/health")
async def health_check() -> dict[str, Any]:
    return {
        "status": "healthy",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "version": config.version,
    }


@app.get("/ready")
async def readiness_check(db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        db.execute(text("SELECT 1"))
        db_healthy = True
    except Exception:
        db_healthy = False
    return {
        "status": "healthy" if db_healthy else "unhealthy",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "version": config.version,
        "checks": {"database": "healthy" if db_healthy else "unhealthy"},
    }


@app.post("/clips/detect")
async def detect_clips(request: Request, authorization: str = Depends(_verify_bearer), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Detect and score clip candidates (Architecture §6 — engine owns ClipScore)."""
    body = await request.json()
    job_id = f"clip-{uuid.uuid4().hex[:12]}"
    video_id = body.get("video_id", "")
    channel_id = body.get("channel_id", "")
    tenant_id = body.get("tenant_id", "")
    segments = body.get("segments") or []
    video_path = body.get("video_path")
    audio_path = body.get("audio_path")

    if not segments and (video_path or audio_path):
        segments = await _run_perception_pipeline(video_path, audio_path)

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

    weights = None
    raw_w = getattr(config, "clip_score_weights_json", "") or ""
    if raw_w.strip():
        try:
            import json as _json
            weights = _json.loads(raw_w)
        except Exception:
            weights = None
    scored = score_highlights(norm, weights=weights)
    candidates = scored.get("scored_segments") or scored.get("candidates") or []

    for c in candidates:
        if "composite" not in c and "score" in c:
            c["composite"] = c["score"]
        c.setdefault("video_id", video_id)

    job = ClipJob(
        job_id=job_id,
        video_id=video_id,
        channel_id=channel_id,
        tenant_id=tenant_id,
        status="completed",
        progress_percent=100,
        candidates=candidates,
        segment_count=len(norm),
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
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
async def get_clip_job_status(job_id: str, authorization: str = Depends(_verify_bearer), db: Session = Depends(get_db)) -> dict[str, Any]:
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
async def get_clip_job_results(job_id: str, authorization: str = Depends(_verify_bearer), db: Session = Depends(get_db)) -> dict[str, Any]:
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
async def get_clip(clip_id: str, authorization: str = Depends(_verify_bearer), db: Session = Depends(get_db)) -> dict[str, Any]:
    jobs = db.query(ClipJob).all()
    for job in jobs:
        for candidate in (job.candidates or []):
            if candidate.get("clip_id") == clip_id:
                return candidate
    raise HTTPException(status_code=404, detail="clip_id not found")


@app.delete("/clips/{clip_id}")
async def delete_clip(clip_id: str, authorization: str = Depends(_verify_bearer), db: Session = Depends(get_db)) -> None:
    jobs = db.query(ClipJob).all()
    for job in jobs:
        for i, candidate in enumerate(job.candidates or []):
            if candidate.get("clip_id") == clip_id:
                candidate["status"] = "archived"
                job.candidates = job.candidates or []
                db.commit()
                return None
    raise HTTPException(status_code=404, detail="clip_id not found")


@app.post("/clips/{clip_id}/render")
async def render_clip(clip_id: str, request: Request, authorization: str = Depends(_verify_bearer), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Queue a clip render job. Real encoding is delegated to media-renderer; never fabricate success URLs."""
    body = await request.json()
    job_id = f"render-{uuid.uuid4().hex[:12]}"
    video_id = body.get("video_id", "")
    render_job = RenderJob(
        job_id=job_id,
        clip_id=clip_id,
        video_id=video_id,
        status="queued",
        progress_percent=0,
        output_url="",
        started_at=datetime.now(timezone.utc),
    )
    db.add(render_job)
    db.commit()
    dispatch_body = dict(body)
    if authorization:
        dispatch_body["_authorization"] = (
            authorization if authorization.startswith("Bearer ") else f"Bearer {authorization}"
        )
    asyncio.create_task(_process_render_job(db, job_id, clip_id, dispatch_body))
    return {
        "job_id": job_id,
        "clip_id": clip_id,
        "status": "queued",
        "progress_percent": 0,
        "output_url": "",
        "started_at": render_job.started_at.isoformat() + "Z" if render_job.started_at else None,
        "completed_at": None,
    }


async def _process_render_job(db: Session, job_id: str, clip_id: str, body: dict) -> None:
    from clipping_engine.config import ServiceConfig
    cfg = ServiceConfig()
    render_job = db.query(RenderJob).filter(RenderJob.job_id == job_id).first()
    if not render_job:
        return
    try:
        render_job.status = "processing"
        render_job.progress_percent = 10
        db.commit()
        source = body.get("source") or {}
        payload = {
            "job_id": job_id,
            "clip_id": clip_id,
            "video_id": body.get("video_id") or getattr(render_job, "video_id", None),
            "channel_id": body.get("channel_id", ""),
            "tenant_id": body.get("tenant_id", ""),
            "project_id": body.get("project_id", ""),
            "output_format": body.get("output_format", "mp4"),
            "resolution": body.get("resolution", "1080p"),
            "source": source,
            "source_path": body.get("source_path") or source.get("path") or source.get("source_path") or "",
            "edl": body.get("edl") or source.get("edl") or body.get("timeline"),
            "profile_name": body.get("profile_name") or "youtube_1080p",
        }
        url = cfg.media_renderer_url.rstrip("/") + "/render"
        headers: dict[str, str] = {}
        auth = body.get("_authorization")
        if auth:
            headers["Authorization"] = str(auth)
        async with httpx.AsyncClient(timeout=cfg.request_timeout_seconds) as client:
            resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code >= 400:
            render_job.status = "failed"
            render_job.error_message = f"media-renderer HTTP {resp.status_code}: {resp.text[:500]}"
            render_job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return
        data = resp.json() if resp.content else {}
        out = data.get("output_url") or (data.get("result") or {}).get("output_url") or ""
        status = data.get("status", "completed")
        if not out and status == "completed":
            render_job.status = "failed"
            render_job.error_message = "media-renderer returned completed without output_url"
            render_job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return
        render_job.status = status if status in ("queued", "processing", "completed", "failed") else "completed"
        render_job.progress_percent = int(data.get("progress_percent") or (100 if out else 50))
        render_job.output_url = out
        if render_job.status in ("completed", "failed"):
            render_job.completed_at = datetime.now(timezone.utc)
        if render_job.status == "failed" and not render_job.error_message:
            render_job.error_message = data.get("error_message") or data.get("error") or "render failed"
        db.commit()
    except Exception as e:
        render_job = db.query(RenderJob).filter(RenderJob.job_id == job_id).first()
        if render_job:
            render_job.status = "failed"
            render_job.error_message = f"render dispatch error: {e}"
            render_job.completed_at = datetime.now(timezone.utc)
            db.commit()


@app.post("/clips/{clip_id}/score")
async def score_clip(clip_id: str, request: Request, authorization: str = Depends(_verify_bearer), db: Session = Depends(get_db)) -> dict[str, Any]:
    body = await request.json()
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
    scores = clip_data.get("scores", {})
    composite = clip_data.get("composite", 0.0)
    return {
        "clip_id": clip_id,
        "overall_score": round(composite, 4),
        "virality_score": round(scores.get("virality", scores.get("composite", 0.0)), 4),
        "engagement_score": round(scores.get("engagement", scores.get("composite", 0.0)), 4),
        "retention_score": round(scores.get("narrative", 0.0), 4),
        "hook_quality": round(scores.get("hook", 0.0), 4),
        "explanation": "Score computed from clip features",
    }


@app.post("/segments")
async def create_segment(request: Request, authorization: str = Depends(_verify_bearer), db: Session = Depends(get_db)) -> dict[str, Any]:
    body = await request.json()
    video_id = (body.get("video_id") or "").strip()
    if not video_id:
        raise HTTPException(status_code=400, detail="video_id is required")
    start = float(body.get("start_time", body.get("start_seconds", 0.0)) or 0.0)
    end = float(body.get("end_time", body.get("end_seconds", 0.0)) or 0.0)
    if end <= start:
        raise HTTPException(status_code=400, detail="end_time must be greater than start_time")
    segment_id = body.get("segment_id") or f"seg-{uuid.uuid4().hex[:12]}"
    existing = db.query(Segment).filter(Segment.segment_id == segment_id).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"segment_id {segment_id} already exists")
    row = Segment(
        segment_id=segment_id,
        video_id=video_id,
        channel_id=str(body.get("channel_id") or ""),
        tenant_id=str(body.get("tenant_id") or ""),
        start_seconds=start,
        end_seconds=end,
        label=str(body.get("label") or "")[:255],
        tags=list(body.get("tags") or []),
        text=str(body.get("text") or ""),
        metadata_json=dict(body.get("metadata") or {}),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "segment_id": row.segment_id,
        "video_id": row.video_id,
        "channel_id": row.channel_id,
        "start_time": row.start_seconds,
        "end_time": row.end_seconds,
        "start_seconds": row.start_seconds,
        "end_seconds": row.end_seconds,
        "label": row.label,
        "tags": row.tags or [],
        "text": row.text or "",
        "created_at": (row.created_at.isoformat() + "Z") if row.created_at else None,
    }


async def _run_perception_pipeline(video_path: str | None, audio_path: str | None) -> list[dict[str, Any]]:
    import os
    import tempfile
    segments = []
    if video_path:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_audio:
            audio_path = tmp_audio.name
        try:
            extract_audio(video_path, output_path=audio_path)
        except Exception as e:
            logger.warning("Audio extraction failed: %s", e)
            audio_path = None
    if audio_path and os.path.exists(audio_path):
        asr_result = transcribe_audio(audio_path)
        transcript_segments = asr_result.get("segments", [])
        diarize_speakers(audio_path)
        detect_shots(video_path or audio_path)
        detect_scenes(video_path or audio_path)
        semantic_result = segment_semantically(transcript_segments)
        semantic_segments = semantic_result.get("semantic_segments", [])
        for i, seg in enumerate(semantic_segments):
            segments.append({
                "segment_id": seg.get("segment_id", f"seg-{i}"),
                "start_seconds": float(seg.get("start_time", 0)),
                "end_seconds": float(seg.get("end_time", 5.0)),
                "text": seg.get("text", ""),
                "visual_change": 0.5,
            })
        if audio_path and os.path.exists(audio_path):
            try:
                os.unlink(audio_path)
            except Exception:
                pass
    return segments

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("clipping_engine.main:app", host="0.0.0.0", port=config.port, reload=False)
