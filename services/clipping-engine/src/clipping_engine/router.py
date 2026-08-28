"""API route handlers for clip detection endpoints.

Separates routing logic from main.py for testability.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from typing import Any

from clipping_engine.models import ClipDetectionRequest, SegmentRequest
from clipping_engine.service import ClipDetectionService

router = APIRouter(prefix="/clips", tags=["clips"])
service = ClipDetectionService()


@router.post("/detect")
async def detect_clips(request: ClipDetectionRequest) -> dict[str, Any]:
    """Detect clip candidates from a long-form video."""
    return await service.create_detection_job(request)


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str) -> dict[str, Any]:
    """Get clip detection job status."""
    job = await service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/jobs/{job_id}/results")
async def get_job_results(job_id: str) -> dict[str, Any]:
    """Get clip detection results."""
    return await service.get_job_results(job_id)


@router.get("/{clip_id}")
async def get_clip(clip_id: str) -> dict[str, Any]:
    """Get a specific clip by ID."""
    clip = await service.get_clip(clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    return clip


@router.delete("/{clip_id}")
async def delete_clip(clip_id: str) -> None:
    """Delete/archive a clip."""
    await service.delete_clip(clip_id)


@router.post("/{clip_id}/render")
async def render_clip(clip_id: str, request: Request) -> dict[str, Any]:
    """Render a clip to final output."""
    body = await request.json()
    return await service.render_clip(clip_id, body)


@router.post("/{clip_id}/score")
async def score_clip(clip_id: str) -> dict[str, Any]:
    """Score a clip for virality/engagement potential."""
    return await service.score_clip(clip_id)


@router.post("/segments")
async def create_segment(request: SegmentRequest) -> dict[str, Any]:
    """Create a manual segment."""
    return await service.create_segment(request)
