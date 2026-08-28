"""Schemas for Content Strategist / Ideation Agent (Architecture §4.2).

Inputs: Market & Audience Intelligence report, research bundle.
Outputs: ContentStrategy, TopicPortfolio, idea set, hook candidates.
Downstream: scripting_agent ScriptRequest (video_title, audience, keywords).
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class VideoConcept(BaseModel):
    title: str
    hook: str
    angle: str = ""
    format: str = "long-form"  # long-form | short | series-episode
    thumbnail_concept: str = ""
    target_keywords: list[str] = Field(default_factory=list)
    estimated_ctr: str = ""
    production_complexity: str = "medium"
    uniqueness_score: float = 0.5
    trend_alignment: str = "medium"
    score: float = 0.0


class TopicPortfolioItem(BaseModel):
    topic: str
    priority: int = 1
    pillar: str = ""
    planned_formats: list[str] = Field(default_factory=list)


class ContentStrategy(BaseModel):
    summary: str = ""
    pillars: list[str] = Field(default_factory=list)
    series_opportunities: list[str] = Field(default_factory=list)
    brand_constraints_checked: bool = True


class IdeationRequest(BaseModel):
    topic: str = ""
    channel_name: str = ""
    target_audience: str = ""
    content_pillars: list[str] = Field(default_factory=list)
    num_concepts: int = 5
    # ResearchBundle-compatible (research_agent output)
    research_brief: dict[str, Any] | str = Field(default_factory=dict)
    # Market & Audience Intelligence report (MAI output shape)
    market_intelligence: dict[str, Any] | None = None
    task_type: str = "ideate"


class IdeationResponse(BaseModel):
    """§4.2: ContentStrategy, TopicPortfolio, idea set, hook candidates."""

    concepts: list[VideoConcept] = Field(default_factory=list)
    recommended_concept: VideoConcept | None = None
    content_strategy: ContentStrategy = Field(default_factory=ContentStrategy)
    topic_portfolio: list[TopicPortfolioItem] = Field(default_factory=list)
    idea_set: list[str] = Field(default_factory=list)
    hook_candidates: list[str] = Field(default_factory=list)
    content_series_potential: bool = False
    seo_optimization_notes: list[str] = Field(default_factory=list)
    # Convenience mapping for scripting_agent handoff
    scripting_handoff: dict[str, Any] = Field(default_factory=dict)
    raw_provider_text: str | None = None
    provider_usage: dict[str, Any] | None = None
