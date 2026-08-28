"""Pydantic model for publication.published event."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PublicationPublished(BaseModel):
    event_id: str
    event_type: str = "publication.published"
    timestamp: datetime
    channel_id: str
    publication_id: str
    asset_id: str
    platform: str = Field(..., pattern=r"^(youtube|tiktok|instagram|twitter)$")
    platform_video_id: str | None = None
    published_url: str | None = None
    scheduled_at: datetime | None = None
    published_at: datetime | None = None
    metadata: dict[str, Any] | None = None
    disclosure_flags: list[str] | None = None
