"""Intelligence domain schemas for SentraAura agents."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass
class TrendSignal:
    """A detected trend signal."""
    signal_id: str
    channel_id: str
    topic: str
    demand_score: float = 0.0
    competition_score: float = 0.0
    freshness_score: float = 0.0
    monetization_score: float = 0.0
    risk_score: float = 0.0
    confidence: float = 0.0
    source: str = ""
    detected_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OpportunityScore:
    """Scored content opportunity."""
    opportunity_id: str
    channel_id: str
    topic: str
    score: float = 0.0
    demand_score: float = 0.0
    audience_fit: float = 0.0
    monetization_fit: float = 0.0
    freshness: float = 0.0
    competition_saturation: float = 0.0
    risk_score: float = 0.0
    recommended_action: str = ""
    confidence: float = 0.0


@dataclass
class PortfolioPlan:
    """Channel-level content portfolio plan."""
    plan_id: str
    channel_id: str
    goals: list[str] = field(default_factory=list)
    topic_quotas: dict[str, int] = field(default_factory=dict)
    budget_allocation: dict[str, float] = field(default_factory=dict)
    content_mix: dict[str, float] = field(default_factory=dict)
    period_start: datetime = field(default_factory=datetime.utcnow)
    period_end: datetime = field(default_factory=datetime.utcnow)
