"""Business logic for media rendering and transcoding.

Encapsulates all domain operations behind a service layer.
Updated to use database-backed storage instead of in-memory dicts.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from media_renderer.models import RenderRequest, TranscodeRequest
from media_renderer.db.models import (
    RenderJobORM,
    TranscodeJobORM,
    RenderTemplateORM,
    orm_to_model_render_job,
    orm_to_model_transcode_job,
    orm_to_model_template,
)
from media_renderer.db.session import get_db


class MediaRendererService:
    """Service layer for media rendering operations.
    
    Uses database-backed storage for jobs and templates.
    """

    def __init__(self) -> None:
        # Default templates
        self._default_templates: list[dict[str, Any]] = [
            {
                "template_id": "standard_1080p",
                "name": "Standard 1080p",
                "description": "Default 1080p render template",
                "compatible_formats": ["mp4", "mov"],
                "default_settings": {"resolution": "1080p", "frame_rate": 30},
            },
        ]
        # Ensure default templates exist in DB
        self._ensure_default_templates()

    def _ensure_default_templates(self) -> None:
        """Ensure default templates exist in the database."""
        db = next(get_db())
        try:
            for template_data in self._default_templates:
                existing = db.query(RenderTemplateORM).filter(
                    RenderTemplateORM.template_id == template_data["template_id"]
                ).first()
                if not existing:
                    orm_template = RenderTemplateORM(
                        template_id=template_data["template_id"],
                        name=template_data["name"],
                        description=template_data["description"],
                        compatible_formats=template_data["compatible_formats"],
                        default_settings=template_data["default_settings"],
                        created_by="system",
                        updated_by="system",
                    )
                    db.add(orm_template)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    async def create_render_job(self, request: RenderRequest) -> dict[str, Any]:
        """Create a new render job in the database."""
        db = next(get_db())
        try:
            job_id = f"render-{uuid.uuid4().hex[:12]}"
            orm_job = RenderJobORM(
                job_id=job_id,
                project_id=request.project_id,
                channel_id=request.channel_id,
                tenant_id=request.tenant_id or "",
                status="queued",
                progress_percent=0,
                output_url="",
                output_format=request.output_format,
                resolution=request.resolution,
                frame_rate=request.frame_rate,
                started_at=datetime.utcnow(),
                completed_at=None,
                render_plan={},
                timeline_clips=0,
                template_id=request.template_id,
                callback_url=request.callback_url,
                created_by=request.channel_id,
                updated_by=request.channel_id,
            )
            db.add(orm_job)
            db.commit()
            db.refresh(orm_job)
            return orm_to_model_render_job(orm_job)
        finally:
            db.close()

    async def get_render_job(self, job_id: str) -> dict[str, Any] | None:
        """Get a render job by ID from the database."""
        db = next(get_db())
        try:
            orm_job = db.query(RenderJobORM).filter(
                RenderJobORM.job_id == job_id,
                RenderJobORM.is_deleted == False
            ).first()
            if orm_job:
                return orm_to_model_render_job(orm_job)
            return None
        finally:
            db.close()

    async def cancel_job(self, job_id: str) -> dict[str, Any]:
        """Cancel a render job."""
        db = next(get_db())
        try:
            orm_job = db.query(RenderJobORM).filter(
                RenderJobORM.job_id == job_id,
                RenderJobORM.is_deleted == False
            ).first()
            if not orm_job:
                return {"job_id": job_id, "status": "not_found"}
            
            orm_job.status = "cancelled"
            orm_job.updated_at = datetime.utcnow()
            db.commit()
            return orm_to_model_render_job(orm_job)
        finally:
            db.close()

    async def list_jobs(
        self,
        channel_id: str | None,
        status: str | None,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        """List render jobs with pagination."""
        db = next(get_db())
        try:
            query = db.query(RenderJobORM).filter(RenderJobORM.is_deleted == False)
            if channel_id:
                query = query.filter(RenderJobORM.channel_id == channel_id)
            if status:
                query = query.filter(RenderJobORM.status == status)
            
            total = query.count()
            start = (page - 1) * page_size
            end = start + page_size
            
            orm_jobs = query.offset(start).limit(page_size).all()
            
            return {
                "items": [orm_to_model_render_job(j) for j in orm_jobs],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": (total + page_size - 1) // page_size,
                },
            }
        finally:
            db.close()

    async def create_transcode_job(self, request: TranscodeRequest) -> dict[str, Any]:
        """Create a new transcode job in the database."""
        db = next(get_db())
        try:
            job_id = f"transcode-{uuid.uuid4().hex[:12]}"
            orm_job = TranscodeJobORM(
                job_id=job_id,
                source_asset_id=request.source_asset_id,
                target_format=request.target_format,
                target_resolution=request.target_resolution,
                target_codec=request.target_codec,
                bitrate_kbps=request.bitrate_kbps,
                status="queued",
                progress_percent=0,
                output_url="",
                started_at=datetime.utcnow(),
                completed_at=None,
                created_by=request.source_asset_id,
                updated_by=request.source_asset_id,
                tenant_id="",
                channel_id="",
            )
            db.add(orm_job)
            db.commit()
            db.refresh(orm_job)
            return orm_to_model_transcode_job(orm_job)
        finally:
            db.close()

    async def list_templates(self) -> list[dict[str, Any]]:
        """List all render templates from the database."""
        db = next(get_db())
        try:
            orm_templates = db.query(RenderTemplateORM).all()
            return [orm_to_model_template(t) for t in orm_templates]
        finally:
            db.close()

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
