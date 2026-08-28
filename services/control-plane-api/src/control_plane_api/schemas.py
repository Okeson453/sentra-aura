"""Pydantic request/response schemas for Control Plane API.

All routes use these typed models for validation, serialization, and OpenAPI generation.
Matches Architecture §3.1 and Backend Spec §3.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ------------------------------------------------------------------
# Shared
# ------------------------------------------------------------------

class PaginationParams(BaseModel):
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    sort_by: str = Field(default="created_at")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")


class PaginatedResponse(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1)
    offset: int = Field(default=0, ge=0)
    has_more: bool = Field(default=False)


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
    code: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: str | None = None


# ------------------------------------------------------------------
# Channel
# ------------------------------------------------------------------

class ChannelStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    ARCHIVED = "ARCHIVED"
    SUSPENDED = "SUSPENDED"


class ChannelPlatform(str, Enum):
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    LINKEDIN = "linkedin"
    TWITTER = "twitter"


class ChannelCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    platform: ChannelPlatform
    tenant_id: str = Field(..., min_length=1, max_length=32)
    platform_channel_id: str | None = Field(default=None, max_length=255)
    niche: str | None = Field(default=None, max_length=255)
    target_audience: str | None = Field(default=None, max_length=2000)
    content_mix: dict[str, float] = Field(default_factory=dict)
    schedule: dict[str, Any] = Field(default_factory=dict)

    @field_validator("content_mix")
    @classmethod
    def _validate_content_mix(cls, v: dict[str, float]) -> dict[str, float]:
        total = sum(v.values())
        if total > 0 and abs(total - 1.0) > 0.001:
            raise ValueError("content_mix values must sum to 1.0")
        return v


class ChannelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: ChannelStatus | None = None
    niche: str | None = Field(default=None, max_length=255)
    target_audience: str | None = Field(default=None, max_length=2000)
    content_mix: dict[str, float] | None = None
    schedule: dict[str, Any] | None = None


class ChannelResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    platform: str
    platform_channel_id: str | None
    status: str
    niche: str | None
    target_audience: str | None
    content_mix: dict[str, float]
    schedule: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    created_by: str | None
    updated_by: str | None


# ------------------------------------------------------------------
# Content Plan
# ------------------------------------------------------------------

class ContentPlanStatus(str, Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ContentPlanCreate(BaseModel):
    channel_id: str = Field(..., min_length=1, max_length=32)
    topic: str = Field(..., min_length=1, max_length=500)
    strategy: dict[str, Any] = Field(default_factory=dict)
    budget: dict[str, Any] = Field(default_factory=dict)
    deadline: datetime | None = None


class ContentPlanUpdate(BaseModel):
    topic: str | None = Field(default=None, min_length=1, max_length=500)
    status: ContentPlanStatus | None = None
    strategy: dict[str, Any] | None = None
    budget: dict[str, Any] | None = None
    deadline: datetime | None = None


class ContentPlanResponse(BaseModel):
    id: str
    channel_id: str
    topic: str
    status: str
    strategy: dict[str, Any]
    budget: dict[str, Any]
    deadline: datetime | None
    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------------
# Script
# ------------------------------------------------------------------

class ScriptStatus(str, Enum):
    DRAFT = "DRAFT"
    REVIEW = "REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ScriptCreate(BaseModel):
    content_plan_id: str = Field(..., min_length=1, max_length=32)
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(default="", max_length=50000)
    word_count: int = Field(default=0, ge=0)
    estimated_duration: int = Field(default=0, ge=0)
    disclosure_tags: list[str] = Field(default_factory=list)


class ScriptUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    content: str | None = Field(default=None, max_length=50000)
    status: ScriptStatus | None = None
    word_count: int | None = Field(default=None, ge=0)
    estimated_duration: int | None = Field(default=None, ge=0)
    disclosure_tags: list[str] | None = None


class ScriptResponse(BaseModel):
    id: str
    content_plan_id: str
    title: str
    content: str
    status: str
    word_count: int
    estimated_duration: int
    disclosure_tags: list[str]
    version: int
    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------------
# Video
# ------------------------------------------------------------------

class VideoStatus(str, Enum):
    RENDERING = "RENDERING"
    RENDERED = "RENDERED"
    FAILED = "FAILED"
    PUBLISHED = "PUBLISHED"


class VideoCreate(BaseModel):
    script_id: str = Field(..., min_length=1, max_length=32)
    channel_id: str = Field(..., min_length=1, max_length=32)
    duration_seconds: int = Field(default=0, ge=0)
    resolution: str = Field(default="1920x1080", pattern=r"^\d+x\d+$")
    asset_manifest: dict[str, Any] = Field(default_factory=dict)


class VideoUpdate(BaseModel):
    status: VideoStatus | None = None
    duration_seconds: int | None = Field(default=None, ge=0)
    resolution: str | None = Field(default=None, pattern=r"^\d+x\d+$")
    asset_manifest: dict[str, Any] | None = None


class VideoResponse(BaseModel):
    id: str
    script_id: str
    channel_id: str
    status: str
    duration_seconds: int
    resolution: str
    asset_manifest: dict[str, Any]
    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------------
# Clip
# ------------------------------------------------------------------

class ClipType(str, Enum):
    HIGHLIGHT = "HIGHLIGHT"
    HOOK = "HOOK"
    TUTORIAL = "TUTORIAL"
    REACTION = "REACTION"
    BEHIND_THE_SCENES = "BEHIND_THE_SCENES"


class ClipCreate(BaseModel):
    video_id: str = Field(..., min_length=1, max_length=32)
    channel_id: str = Field(..., min_length=1, max_length=32)
    clip_type: ClipType = ClipType.HIGHLIGHT
    start_ms: int = Field(default=0, ge=0)
    end_ms: int = Field(default=0, ge=0)
    duration_ms: int = Field(default=0, ge=0)
    aspect_ratio: str = Field(default="9:16", pattern=r"^\d+:\d+$")
    scores: dict[str, float] = Field(default_factory=dict)
    lineage: dict[str, Any] = Field(default_factory=dict)


class ClipUpdate(BaseModel):
    status: str | None = None
    start_ms: int | None = Field(default=None, ge=0)
    end_ms: int | None = Field(default=None, ge=0)
    duration_ms: int | None = Field(default=None, ge=0)
    aspect_ratio: str | None = Field(default=None, pattern=r"^\d+:\d+$")
    scores: dict[str, float] | None = None
    lineage: dict[str, Any] | None = None


class ClipResponse(BaseModel):
    id: str
    video_id: str
    channel_id: str
    clip_type: str
    status: str
    start_ms: int
    end_ms: int
    duration_ms: int
    aspect_ratio: str
    scores: dict[str, float]
    lineage: dict[str, Any]
    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------------
# Publication
# ------------------------------------------------------------------

class PublicationStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    PUBLISHING = "PUBLISHING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    UNPUBLISHED = "UNPUBLISHED"


class PublicationCreate(BaseModel):
    channel_id: str = Field(..., min_length=1, max_length=32)
    video_id: str | None = Field(default=None, min_length=1, max_length=32)
    clip_id: str | None = Field(default=None, min_length=1, max_length=32)
    platform: str = Field(..., min_length=1, max_length=50)
    scheduled_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PublicationUpdate(BaseModel):
    status: PublicationStatus | None = None
    scheduled_at: datetime | None = None
    metadata: dict[str, Any] | None = None


class PublicationResponse(BaseModel):
    id: str
    channel_id: str
    video_id: str | None
    clip_id: str | None
    platform: str
    platform_id: str | None
    platform_url: str | None
    status: str
    scheduled_at: datetime | None
    published_at: datetime | None
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------------
# Performance
# ------------------------------------------------------------------

class PerformanceCreate(BaseModel):
    publication_id: str = Field(..., min_length=1, max_length=32)
    channel_id: str = Field(..., min_length=1, max_length=32)
    views: int = Field(default=0, ge=0)
    watch_time_seconds: int = Field(default=0, ge=0)
    retention_curve: list[float] = Field(default_factory=list)
    ctr: float = Field(default=0.0, ge=0.0, le=1.0)
    engagement_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    subscriber_gain: int = Field(default=0)
    traffic_sources: dict[str, Any] = Field(default_factory=dict)


class PerformanceResponse(BaseModel):
    id: str
    publication_id: str
    channel_id: str
    views: int
    watch_time_seconds: int
    retention_curve: list[float]
    ctr: float
    engagement_rate: float
    subscriber_gain: int
    traffic_sources: dict[str, Any]
    measured_at: datetime


# ------------------------------------------------------------------
# Experiment
# ------------------------------------------------------------------

class ExperimentStatus(str, Enum):
    DRAFT = "DRAFT"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ExperimentCreate(BaseModel):
    channel_id: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=255)
    hypothesis: str = Field(default="", max_length=2000)
    variant_ids: list[str] = Field(default_factory=list)
    control_id: str | None = Field(default=None, max_length=32)
    asset_id: str | None = Field(default=None, max_length=32)
    metrics: list[str] = Field(default_factory=list)
    required_sample_size: int = Field(default=1000, ge=100)
    start_time: datetime | None = None
    end_time: datetime | None = None


class ExperimentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    hypothesis: str | None = Field(default=None, max_length=2000)
    status: ExperimentStatus | None = None
    variant_ids: list[str] | None = None
    control_id: str | None = Field(default=None, max_length=32)
    asset_id: str | None = Field(default=None, max_length=32)
    metrics: list[str] | None = None
    required_sample_size: int | None = Field(default=None, ge=100)
    start_time: datetime | None = None
    end_time: datetime | None = None
    results: dict[str, Any] | None = None


class ExperimentResponse(BaseModel):
    id: str
    channel_id: str
    name: str
    hypothesis: str
    variant_ids: list[str]
    control_id: str | None
    asset_id: str | None
    metrics: list[str]
    status: str
    start_time: datetime | None
    end_time: datetime | None
    required_sample_size: int
    results: dict[str, Any]
    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------------
# Policy
# ------------------------------------------------------------------

class AutonomyLevel(str, Enum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"


class PolicyType(str, Enum):
    AUTONOMY = "autonomy"
    CONTENT = "content"
    PUBLISHING = "publishing"
    COST = "cost"
    BRAND = "brand"
    LEGAL = "legal"


class PolicyCreate(BaseModel):
    channel_id: str = Field(..., min_length=1, max_length=32)
    policy_type: PolicyType
    autonomy_level: AutonomyLevel = AutonomyLevel.L1
    rules: dict[str, Any] = Field(default_factory=dict)
    weights: dict[str, float] = Field(default_factory=dict)


class PolicyUpdate(BaseModel):
    policy_type: PolicyType | None = None
    autonomy_level: AutonomyLevel | None = None
    rules: dict[str, Any] | None = None
    weights: dict[str, float] | None = None
    status: str | None = Field(default=None, pattern="^(ACTIVE|INACTIVE)$")


class PolicyResponse(BaseModel):
    id: str
    channel_id: str
    policy_type: str
    autonomy_level: str
    rules: dict[str, Any]
    weights: dict[str, float]
    version: int
    status: str
    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------------
# Decision Log
# ------------------------------------------------------------------

class DecisionLogCreate(BaseModel):
    channel_id: str = Field(..., min_length=1, max_length=32)
    agent_type: str = Field(..., min_length=1, max_length=50)
    decision: str = Field(..., min_length=1, max_length=2000)
    reasoning: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    alternatives_rejected: list[str] = Field(default_factory=list)
    human_override_possible: bool = True


class DecisionLogOverride(BaseModel):
    override_status: str = Field(..., pattern="^(APPROVED|REJECTED|ESCALATED)$")
    override_reason: str = Field(default="", max_length=2000)


class DecisionLogResponse(BaseModel):
    id: str
    channel_id: str
    agent_type: str
    decision: str
    reasoning: list[dict[str, Any]]
    confidence: float
    alternatives_rejected: list[str]
    human_override_possible: bool
    override_status: str
    override_by: str | None
    override_at: datetime | None
    created_at: datetime


# ------------------------------------------------------------------
# Analytics
# ------------------------------------------------------------------

class ChannelAnalyticsResponse(BaseModel):
    channel_id: str
    total_views: int
    total_watch_time_seconds: int
    total_subscriber_gain: int
    publication_count: int
    avg_ctr: float
    avg_engagement_rate: float
    period_start: datetime | None
    period_end: datetime | None


class TrendAnalyticsResponse(BaseModel):
    channel_id: str
    topic: str
    demand_score: float
    competition_score: float
    freshness_score: float
    monetization_score: float
    confidence: float
    recommended_action: str
