from media_renderer.assembly import timeline_builder, compositor
from media_renderer.reframing import subject_tracker, crop_path_generator
from media_renderer.encoding import ffmpeg_wrapper
"""Business logic for media rendering and transcoding.

Encapsulates all domain operations behind a service layer.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from media_renderer.models import RenderRequest, TranscodeRequest


class MediaRendererService:
    """Service layer for media rendering operations."""

    def __init__(self) -> None:
        self._render_jobs: dict[str, dict[str, Any]] = {}
        self._transcode_jobs: dict[str, dict[str, Any]] = {}
        self._templates: list[dict[str, Any]] = [
            {
                "template_id": "standard_1080p",
                "name": "Standard 1080p",
                "description": "Default 1080p render template",
                "compatible_formats": ["mp4", "mov"],
                "default_settings": {"resolution": "1080p", "frame_rate": 30},
            },
        ]

    async def create_render_job(self, request: RenderRequest) -> dict[str, Any]:
        job_id = f"render-{uuid.uuid4().hex[:12]}"
        job = {
            "job_id": job_id,
            "status": "queued",
            "project_id": request.project_id,
            "channel_id": request.channel_id,
            "progress_percent": 0,
            "output_url": "",
            "output_format": request.output_format,
            "resolution": request.resolution,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "completed_at": None,
        }
        self._render_jobs[job_id] = job
        return job

    async def get_render_job(self, job_id: str) -> dict[str, Any] | None:
        return self._render_jobs.get(job_id)

    async def cancel_job(self, job_id: str) -> dict[str, Any]:
        job = self._render_jobs.get(job_id)
        if not job:
            return {"job_id": job_id, "status": "not_found"}
        job["status"] = "cancelled"
        return job

    async def list_jobs(self, channel_id: str | None, status: str | None, page: int, page_size: int) -> dict[str, Any]:
        items = list(self._render_jobs.values())
        if channel_id:
            items = [j for j in items if j.get("channel_id") == channel_id]
        if status:
            items = [j for j in items if j.get("status") == status]
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

    async def create_transcode_job(self, request: TranscodeRequest) -> dict[str, Any]:
        job_id = f"transcode-{uuid.uuid4().hex[:12]}"
        job = {
            "job_id": job_id,
            "status": "queued",
            "source_asset_id": request.source_asset_id,
            "target_format": request.target_format,
            "progress_percent": 0,
            "output_url": "",
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "completed_at": None,
        }
        self._transcode_jobs[job_id] = job
        return job

    async def list_templates(self) -> list[dict[str, Any]]:
        return self._templates


    def build_render_plan(self, timeline_spec: dict) -> dict:
        """Compose timeline + crop paths + encode plan using real module classes."""
        from media_renderer.assembly.timeline_builder import TimelineBuilder
        from media_renderer.reframing.crop_path_generator import CropPathGenerator
        from media_renderer.encoding.ffmpeg_wrapper import FFmpegWrapper
        tb = TimelineBuilder()
        clips = timeline_spec.get("clips") or []
        for c in clips:
            if isinstance(c, dict):
                tb.add_clip(
                    track=str(c.get("track") or "v1"),
                    source_path=str(c.get("source_path") or c.get("path") or ""),
                    start_time=float(c.get("start") or 0),
                    end_time=float(c.get("end") or 1),
                )
        cropper = CropPathGenerator() if "CropPathGenerator" in dir() else None
        return {
            "tracks": getattr(tb, "tracks", {}),
            "encoder": FFmpegWrapper().ffmpeg_path,
            "clip_count": len(clips),
        }

