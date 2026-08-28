"""Agent contracts for the Clipping domain.

Defines the interface between the Clipping Agent and the orchestrator.
Matches Architecture §5.4 and §14.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ClipType(str, Enum):
    HOOK = "HOOK"
    HIGHLIGHT = "HIGHLIGHT"
    REACTION = "REACTION"
    TUTORIAL = "TUTORIAL"
    BEHIND_THE_SCENES = "BEHIND_THE_SCENES"
    SHORT_FORM = "SHORT_FORM"


class ClipStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    READY = "READY"
    REJECTED = "REJECTED"
    PUBLISHED = "PUBLISHED"


@dataclass
class ClipRequest:
    """Request for the Clipping Agent to generate clips."""
    video_id: str = ""
    channel_id: str = ""
    tenant_id: str = ""
    clip_types: list[ClipType] = field(default_factory=lambda: [ClipType.HOOK, ClipType.HIGHLIGHT])
    target_platforms: list[str] = field(default_factory=lambda: ["youtube_shorts", "tiktok", "instagram_reels"])
    min_duration_seconds: float = 15.0
    max_duration_seconds: float = 60.0
    aspect_ratios: list[str] = field(default_factory=lambda: ["9:16", "1:1"])
    scoring_weights: dict[str, float] = field(default_factory=lambda: {
        "engagement": 0.35,
        "retention": 0.30,
        "shareability": 0.20,
        "brand_safety": 0.15,
    })
    metadata: dict[str, Any] = field(default_factory=dict)
    requested_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ClipResult:
    """Result from the Clipping Agent."""
    clip_id: str = ""
    video_id: str = ""
    channel_id: str = ""
    clip_type: ClipType = ClipType.HOOK
    status: ClipStatus = ClipStatus.PENDING
    start_seconds: float = 0.0
    end_seconds: float = 0.0
    duration_seconds: float = 0.0
    aspect_ratio: str = "9:16"
    scores: dict[str, float] = field(default_factory=dict)
    transcript: str = ""
    thumbnail_asset_id: str = ""
    video_asset_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None


@dataclass
class ClipBatchRequest:
    """Batch request for multiple clips."""
    requests: list[ClipRequest] = field(default_factory=list)
    batch_id: str = ""
    priority: int = 5
    max_parallel: int = 3
    timeout_seconds: float = 300.0


@dataclass
class ClipBatchResult:
    """Batch result for multiple clips."""
    batch_id: str = ""
    results: list[ClipResult] = field(default_factory=list)
    failed: list[dict[str, Any]] = field(default_factory=list)
    completed_at: datetime = field(default_factory=datetime.utcnow)
