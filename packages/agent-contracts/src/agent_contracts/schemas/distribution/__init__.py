"""Distribution domain schemas for SentraAura agents."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ThumbnailVariant:
    """A generated thumbnail variant."""
    variant_id: str
    video_id: str
    image_url: str = ""
    predicted_ctr: float = 0.0
    style: str = ""
    status: str = "READY"


@dataclass
class SEOMetadata:
    """SEO-optimized metadata for a publication."""
    metadata_id: str
    video_id: str
    title: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    chapters: list[dict[str, Any]] = field(default_factory=list)
    category: str = ""
    disclosure_text: str = ""
    language: str = "en"


@dataclass
class Publication:
    """A published asset record."""
    publication_id: str
    channel_id: str
    video_id: str = ""
    clip_id: str = ""
    platform: str = "youtube"
    platform_id: str = ""
    platform_url: str = ""
    status: str = "SCHEDULED"
    scheduled_at: datetime | None = None
    published_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
