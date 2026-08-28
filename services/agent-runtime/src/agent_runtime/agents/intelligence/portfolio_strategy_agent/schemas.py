"""Schemas for Portfolio Strategy Agent (Architecture §4.2).

Outputs: portfolio plan, topic quotas, budget allocation.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChannelAllocation(BaseModel):
    channel_id: str
    budget_usd: float
    video_count: int = 0
    priority: int = 1
    topic_quota: dict[str, int] = Field(default_factory=dict)


class PortfolioPlanRequest(BaseModel):
    """Inputs: channel goals, historical performance, budget (§4.2)."""

    portfolio_name: str = "Default"
    total_budget_usd: float = 1000.0
    channels: list[dict[str, Any]] = Field(default_factory=list)
    content_themes: list[str] = Field(default_factory=list)
    planning_period_days: int = 30
    risk_tolerance: str = "medium"
    # Optional richer inputs
    channel_goals: list[dict[str, Any]] = Field(default_factory=list)
    historical_performance: dict[str, Any] | str | None = None
    market_intelligence: dict[str, Any] | None = None
    max_videos_per_week: int | None = None
    task_type: str = "plan"


class PortfolioPlanResponse(BaseModel):
    """§4.2: portfolio plan, topic quotas, budget allocation (+ planning detail)."""

    portfolio_plan_summary: str
    channel_allocations: list[ChannelAllocation] = Field(default_factory=list)
    topic_quotas: dict[str, int] = Field(default_factory=dict)
    budget_allocation: dict[str, float] = Field(default_factory=dict)
    cross_channel_themes: list[str] = Field(default_factory=list)
    content_calendar: list[dict[str, Any]] = Field(default_factory=list)
    risk_assessment: list[str] = Field(default_factory=list)
    success_metrics: dict[str, Any] = Field(default_factory=dict)
    # Shape expected when passed as executive_orchestrator portfolio_plan payload
    portfolio_plan: dict[str, Any] = Field(default_factory=dict)
    emphasize_distribution: bool = False
    raw_provider_text: str | None = None
    provider_usage: dict[str, Any] | None = None
