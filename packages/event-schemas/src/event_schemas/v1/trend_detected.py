"""Pydantic model for trend.detected event."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TrendSignal(BaseModel):
    signal_id: str
    source: str = Field(..., pattern=r"^(youtube_trends|google_trends|rss_news|social_listening|competitor_analysis)$")
    query: str
    demand_score: float = Field(..., ge=0.0, le=1.0)
    competition_score: float = Field(..., ge=0.0, le=1.0)
    freshness_score: float = Field(..., ge=0.0, le=1.0)
    monetization_score: float = Field(..., ge=0.0, le=1.0)
    risk_score: float = Field(..., ge=0.0, le=1.0)
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    raw_data: dict[str, Any] | None = None


class TrendDetected(BaseModel):
    event_id: str
    event_type: str = "trend.detected"
    timestamp: datetime
    channel_id: str
    topic_id: str
    trend_signal: TrendSignal
