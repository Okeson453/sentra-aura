"""Agent contracts for the Creative domain.

Defines the interface between the Creative Agent and the orchestrator.
Matches Architecture §5.3 and §14.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class CreativeAssetType(str, Enum):
    SCRIPT = "SCRIPT"
    THUMBNAIL = "THUMBNAIL"
    TITLE = "TITLE"
    DESCRIPTION = "DESCRIPTION"
    TAGS = "TAGS"
    END_SCREEN = "END_SCREEN"
    CARDS = "CARDS"


class CreativeStatus(str, Enum):
    DRAFT = "DRAFT"
    REVIEW = "REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"


@dataclass
class CreativeRequest:
    """Request for the Creative Agent to generate creative assets."""
    content_plan_id: str = ""
    channel_id: str = ""
    tenant_id: str = ""
    asset_types: list[CreativeAssetType] = field(default_factory=lambda: [CreativeAssetType.SCRIPT])
    topic: str = ""
    target_audience: str = ""
    tone: str = "informative"
    duration_target_minutes: float = 10.0
    keywords: list[str] = field(default_factory=list)
    reference_video_ids: list[str] = field(default_factory=list)
    brand_guidelines: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    requested_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CreativeResult:
    """Result from the Creative Agent."""
    asset_id: str = ""
    content_plan_id: str = ""
    channel_id: str = ""
    asset_type: CreativeAssetType = CreativeAssetType.SCRIPT
    status: CreativeStatus = CreativeStatus.DRAFT
    content: str = ""
    word_count: int = 0
    estimated_duration_seconds: float = 0.0
    sentiment_score: float = 0.0
    readability_score: float = 0.0
    seo_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    reviewed_at: datetime | None = None
    reviewed_by: str = ""


@dataclass
class CreativeBatchRequest:
    """Batch request for creative assets."""
    requests: list[CreativeRequest] = field(default_factory=list)
    batch_id: str = ""
    priority: int = 5
    max_parallel: int = 2


@dataclass
class CreativeBatchResult:
    """Batch result for creative assets."""
    batch_id: str = ""
    results: list[CreativeResult] = field(default_factory=list)
    failed: list[dict[str, Any]] = field(default_factory=list)
    completed_at: datetime = field(default_factory=datetime.utcnow)
