"""Operations domain schemas for SentraAura agents."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class PerformanceRecord:
    """Performance metrics for a published asset."""
    record_id: str
    publication_id: str
    channel_id: str
    views: int = 0
    watch_time_seconds: int = 0
    retention_curve: list[float] = field(default_factory=list)
    ctr: float = 0.0
    engagement_rate: float = 0.0
    subscriber_gain: int = 0
    traffic_sources: dict[str, Any] = field(default_factory=dict)
    measured_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Experiment:
    """An A/B or multivariate experiment."""
    experiment_id: str
    channel_id: str
    hypothesis: str = ""
    variant_ids: list[str] = field(default_factory=list)
    control_id: str = ""
    asset_id: str = ""
    metrics: list[str] = field(default_factory=list)
    start_time: datetime | None = None
    end_time: datetime | None = None
    required_sample_size: int = 1000
    status: str = "DRAFT"


@dataclass
class PolicySnapshot:
    """A versioned learned policy snapshot."""
    snapshot_id: str
    channel_id: str
    policy_type: str = ""
    weights: dict[str, float] = field(default_factory=dict)
    version: int = 1
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionLog:
    """Log of an autonomous decision for audit."""
    decision_id: str
    agent_type: str
    decision: str
    reasoning: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    alternatives_rejected: list[str] = field(default_factory=list)
    human_override_possible: bool = True
    channel_id: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
