"""API route handlers for render and transcode endpoints.

Separates routing logic from main.py for testability.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from typing import Any

from media_renderer.models import RenderRequest, TranscodeRequest
from media_renderer.service import MediaRendererService

router = APIRouter(tags=["render"])
service = MediaRendererService()


@router.post("/render")
async def submit_render_job(request: RenderRequest) -> dict[str, Any]:
    """Submit a render job."""
    return await service.create_render_job(request)


@router.get("/render/jobs/{job_id}")
async def get_render_job(job_id: str) -> dict[str, Any]:
    """Get render job status."""
    job = await service.get_render_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/render/jobs/{job_id}/cancel")
async def cancel_render_job(job_id: str) -> dict[str, Any]:
    """Cancel a render job."""
    return await service.cancel_job(job_id)


@router.get("/render/jobs")
async def list_render_jobs(
    channel_id: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """List render jobs."""
    return await service.list_jobs(channel_id, status, page, page_size)


@router.post("/transcode")
async def submit_transcode_job(request: TranscodeRequest) -> dict[str, Any]:
    """Submit a transcode job."""
    return await service.create_transcode_job(request)


@router.get("/templates")
async def list_templates() -> list[dict[str, Any]]:
    """List available render templates."""
    return await service.list_templates()
