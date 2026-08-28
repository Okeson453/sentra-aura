"""Data models for render and transcode jobs.

Pydantic models for request/response validation.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RenderRequest(BaseModel):
    """Request to submit a render job."""
    project_id: str = Field(..., min_length=1, max_length=255)
    channel_id: str = Field(..., min_length=1, max_length=255)
    tenant_id: str = Field(default="", max_length=255)
    output_format: str = Field(default="mp4", max_length=16)
    resolution: str = Field(default="1080p", max_length=16)
    frame_rate: int = Field(default=30, ge=1, le=120)
    template_id: str | None = Field(default=None)
    callback_url: str | None = Field(default=None)


class TranscodeRequest(BaseModel):
    """Request to submit a transcode job."""
    source_asset_id: str = Field(..., min_length=1)
    target_format: str = Field(default="mp4", max_length=16)
    target_resolution: str = Field(default="1080p", max_length=16)
    target_codec: str = Field(default="h264", max_length=16)
    bitrate_kbps: int | None = Field(default=None)


class RenderJob(BaseModel):
    """A render job record."""
    job_id: str = Field(...)
    status: str = Field(default="queued")
    project_id: str = Field(default="")
    channel_id: str = Field(default="")
    progress_percent: int = Field(default=0, ge=0, le=100)
    output_url: str = Field(default="")
    output_format: str = Field(default="mp4")
    resolution: str = Field(default="1080p")
    started_at: str = Field(default="")
    completed_at: str | None = Field(default=None)
    error_message: str | None = Field(default=None)


class RenderTemplate(BaseModel):
    """A render template definition."""
    template_id: str = Field(...)
    name: str = Field(...)
    description: str = Field(default="")
    compatible_formats: list[str] = Field(default_factory=list)
    default_settings: dict[str, Any] = Field(default_factory=dict)
