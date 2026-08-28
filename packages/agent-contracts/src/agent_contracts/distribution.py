"""Agent contracts for the Distribution domain.

Defines the interface between the Distribution Agent and the orchestrator.
Matches Architecture §5.5 and §14.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class DistributionPlatform(str, Enum):
    YOUTUBE = "YOUTUBE"
    TIKTOK = "TIKTOK"
    INSTAGRAM = "INSTAGRAM"
    TWITTER = "TWITTER"
    LINKEDIN = "LINKEDIN"
    FACEBOOK = "FACEBOOK"
    PODCAST = "PODCAST"
    NEWSLETTER = "NEWSLETTER"


class DistributionStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    PUBLISHING = "PUBLISHING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class DistributionRequest:
    """Request for the Distribution Agent to publish content."""
    asset_id: str = ""
    channel_id: str = ""
    tenant_id: str = ""
    platforms: list[DistributionPlatform] = field(default_factory=list)
    schedule_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    requested_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DistributionResult:
    """Result from the Distribution Agent."""
    publication_id: str = ""
    asset_id: str = ""
    channel_id: str = ""
    platform: DistributionPlatform = DistributionPlatform.YOUTUBE
    platform_id: str = ""
    platform_url: str = ""
    status: DistributionStatus = DistributionStatus.SCHEDULED
    scheduled_at: datetime | None = None
    published_at: datetime | None = None
    error_message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DistributionBatchRequest:
    """Batch request for distribution."""
    requests: list[DistributionRequest] = field(default_factory=list)
    batch_id: str = ""
    priority: int = 5
    max_parallel: int = 5


@dataclass
class DistributionBatchResult:
    """Batch result for distribution."""
    batch_id: str = ""
    results: list[DistributionResult] = field(default_factory=list)
    failed: list[dict[str, Any]] = field(default_factory=list)
    completed_at: datetime = field(default_factory=datetime.utcnow)
