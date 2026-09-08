"""SQLAlchemy ORM models for Media Renderer.

Database models for render jobs and transcode jobs.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, JSON, Text
from sqlalchemy.orm import relationship

from media_renderer.db.base import Base, AuditMixin, TenantMixin, SoftDeleteMixin, generate_short_id


class RenderJobORM(Base, AuditMixin, TenantMixin, SoftDeleteMixin):
    """SQLAlchemy ORM model for render jobs."""
    __tablename__ = "render_jobs"

    job_id = Column(String(32), primary_key=True, index=True)
    project_id = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="queued", index=True)
    progress_percent = Column(Integer, nullable=False, default=0)
    output_url = Column(String(1024), nullable=False, default="")
    output_format = Column(String(16), nullable=False, default="mp4")
    resolution = Column(String(16), nullable=False, default="1080p")
    frame_rate = Column(Integer, nullable=False, default=30)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    render_plan = Column(JSON, nullable=False, default={})
    timeline_clips = Column(Integer, nullable=False, default=0)
    template_id = Column(String(64), nullable=True)
    callback_url = Column(String(512), nullable=True)


class TranscodeJobORM(Base, AuditMixin, TenantMixin, SoftDeleteMixin):
    """SQLAlchemy ORM model for transcode jobs."""
    __tablename__ = "transcode_jobs"

    job_id = Column(String(32), primary_key=True, index=True)
    source_asset_id = Column(String(64), nullable=False, index=True)
    target_format = Column(String(16), nullable=False, default="mp4")
    target_resolution = Column(String(16), nullable=False, default="1080p")
    target_codec = Column(String(16), nullable=False, default="h264")
    bitrate_kbps = Column(Integer, nullable=True)
    status = Column(String(32), nullable=False, default="queued", index=True)
    progress_percent = Column(Integer, nullable=False, default=0)
    output_url = Column(String(1024), nullable=False, default="")
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)


class RenderTemplateORM(Base, AuditMixin):
    """SQLAlchemy ORM model for render templates."""
    __tablename__ = "render_templates"

    template_id = Column(String(64), primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    description = Column(String(512), nullable=False, default="")
    compatible_formats = Column(JSON, nullable=False, default=[])
    default_settings = Column(JSON, nullable=False, default={})


# Conversion functions for backwards compatibility
from media_renderer.models import RenderJob as RenderJobModel, TranscodeRequest


def orm_to_model_render_job(orm: RenderJobORM) -> dict[str, Any]:
    """Convert RenderJobORM to dict format."""
    return {
        "job_id": orm.job_id,
        "status": orm.status,
        "project_id": orm.project_id,
        "channel_id": orm.channel_id,
        "tenant_id": orm.tenant_id,
        "progress_percent": orm.progress_percent,
        "output_url": orm.output_url,
        "output_format": orm.output_format,
        "resolution": orm.resolution,
        "frame_rate": orm.frame_rate,
        "started_at": orm.started_at.isoformat() if orm.started_at else "",
        "completed_at": orm.completed_at.isoformat() if orm.completed_at else None,
        "error_message": orm.error_message,
        "render_plan": orm.render_plan,
        "timeline_clips": orm.timeline_clips,
        "template_id": orm.template_id,
        "callback_url": orm.callback_url,
    }


def orm_to_model_transcode_job(orm: TranscodeJobORM) -> dict[str, Any]:
    """Convert TranscodeJobORM to dict format."""
    return {
        "job_id": orm.job_id,
        "source_asset_id": orm.source_asset_id,
        "target_format": orm.target_format,
        "target_resolution": orm.target_resolution,
        "target_codec": orm.target_codec,
        "bitrate_kbps": orm.bitrate_kbps,
        "status": orm.status,
        "progress_percent": orm.progress_percent,
        "output_url": orm.output_url,
        "started_at": orm.started_at.isoformat() if orm.started_at else "",
        "completed_at": orm.completed_at.isoformat() if orm.completed_at else None,
        "error_message": orm.error_message,
    }


def orm_to_model_template(orm: RenderTemplateORM) -> dict[str, Any]:
    """Convert RenderTemplateORM to dict format."""
    return {
        "template_id": orm.template_id,
        "name": orm.name,
        "description": orm.description,
        "compatible_formats": orm.compatible_formats,
        "default_settings": orm.default_settings,
    }
