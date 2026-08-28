"""Data models for clip detection jobs and results.

Pydantic models for request/response validation.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ClipDetectionRequest(BaseModel):
    """Request to detect clips from a video."""
    video_id: str = Field(..., min_length=1, max_length=255)
    channel_id: str = Field(..., min_length=1, max_length=255)
    tenant_id: str = Field(default="", max_length=255)
    min_duration_seconds: float = Field(default=15.0, ge=5.0, le=300.0)
    max_duration_seconds: float = Field(default=60.0, ge=10.0, le=600.0)
    target_clip_count: int = Field(default=5, ge=1, le=20)
    algorithm: str = Field(default="engagement_curve", max_length=64)
    callback_url: str | None = Field(default=None)


class ClipCandidate(BaseModel):
    """A detected clip candidate."""
    clip_id: str = Field(...)
    start_time: float = Field(..., ge=0.0)
    end_time: float = Field(..., ge=0.0)
    duration: float = Field(..., ge=0.0)
    virality_score: float = Field(..., ge=0.0, le=1.0)
    engagement_score: float = Field(..., ge=0.0, le=1.0)
    hook_quality: float = Field(..., ge=0.0, le=1.0)
    transcript_segment: str = Field(default="")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClipDetectionJob(BaseModel):
    """A clip detection job record."""
    job_id: str = Field(...)
    status: str = Field(default="queued")
    video_id: str = Field(default="")
    channel_id: str = Field(default="")
    progress_percent: int = Field(default=0, ge=0, le=100)
    candidates: list[ClipCandidate] = Field(default_factory=list)
    started_at: str = Field(default="")
    completed_at: str | None = Field(default=None)
    error_message: str | None = Field(default=None)


class SegmentRequest(BaseModel):
    """Request to create a manual segment."""
    video_id: str = Field(..., min_length=1)
    start_time: float = Field(..., ge=0.0)
    end_time: float = Field(..., ge=0.0)
    label: str = Field(default="", max_length=255)
    tags: list[str] = Field(default_factory=list)
