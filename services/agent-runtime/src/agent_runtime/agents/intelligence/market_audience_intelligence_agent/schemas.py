"""Schemas for Market & Audience Intelligence Agent (Architecture §4.2 outputs)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TrendSignal(BaseModel):
    """Ranked trend signal from the Data Ingestion Pipeline feed."""

    topic: str
    velocity: float = 0.0
    saturation: float = 0.0
    opportunity_score: float = 0.0  # 0–100 per Architecture §4.2
    confidence: str = "medium"
    volume: int = 0
    source: str = "data_ingestion_pipeline"


class IntelligenceRequest(BaseModel):
    market_segment: str = "general"
    channels_of_interest: list[str] = Field(default_factory=list)
    competitor_channels: list[str] = Field(default_factory=list)
    time_window_days: int = 30
    depth: str = "standard"
    geo: str = "US"
    task_type: str = "analyze"


class IntelligenceResponse(BaseModel):
    """Outputs: opportunity scores, ranked TrendSignal, competitor gaps, audience personas."""

    market_summary: str
    top_trends: list[TrendSignal] = Field(default_factory=list)
    opportunity_scores: list[dict[str, Any]] = Field(default_factory=list)
    audience_segments: list[dict[str, Any]] = Field(default_factory=list)
    competitor_gaps: list[str] = Field(default_factory=list)
    keyword_opportunities: list[str] = Field(default_factory=list)
    content_recommendations: list[str] = Field(default_factory=list)
    confidence_assessment: dict[str, str] = Field(default_factory=dict)
    ingestion_jobs: list[dict[str, Any]] = Field(default_factory=list)
    raw_provider_text: str | None = None
    provider_usage: dict[str, Any] | None = None
