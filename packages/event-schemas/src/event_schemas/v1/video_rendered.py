"""Pydantic model for video.rendered event."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class VideoRendered(BaseModel):
    event_id: str
    event_type: str = "video.rendered"
    timestamp: datetime
    channel_id: str
    video_id: str
    script_id: str
    duration_seconds: int
    resolution: str
    file_size_mb: float
    render_time_seconds: int
    qc_status: str = "pending"
    asset_urls: dict[str, Any] | None = None
