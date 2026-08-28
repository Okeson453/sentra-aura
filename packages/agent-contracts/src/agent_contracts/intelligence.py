"""Agent contracts for the Intelligence domain.

Defines the interface between the Intelligence Agent and the orchestrator.
Matches Architecture §5.1 and §14.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class IntelligenceTaskType(str, Enum):
    TREND_ANALYSIS = "TREND_ANALYSIS"
    COMPETITOR_ANALYSIS = "COMPETITOR_ANALYSIS"
    AUDIENCE_INSIGHT = "AUDIENCE_INSIGHT"
    CONTENT_GAP = "CONTENT_GAP"
    PERFORMANCE_FORECAST = "PERFORMANCE_FORECAST"
    OPTIMIZATION = "OPTIMIZATION"


class IntelligenceStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class IntelligenceRequest:
    """Request for the Intelligence Agent to perform analysis."""
    channel_id: str = ""
    tenant_id: str = ""
    task_type: IntelligenceTaskType = IntelligenceTaskType.TREND_ANALYSIS
    parameters: dict[str, Any] = field(default_factory=dict)
    lookback_days: int = 30
    metadata: dict[str, Any] = field(default_factory=dict)
    requested_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class IntelligenceResult:
    """Result from the Intelligence Agent."""
    result_id: str = ""
    channel_id: str = ""
    task_type: IntelligenceTaskType = IntelligenceTaskType.TREND_ANALYSIS
    status: IntelligenceStatus = IntelligenceStatus.PENDING
    insights: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[dict[str, Any]] = field(default_factory=list)
    confidence_score: float = 0.0
    data_sources: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None


@dataclass
class IntelligenceBatchRequest:
    """Batch request for intelligence tasks."""
    requests: list[IntelligenceRequest] = field(default_factory=list)
    batch_id: str = ""
    priority: int = 5
    max_parallel: int = 3


@dataclass
class IntelligenceBatchResult:
    """Batch result for intelligence tasks."""
    batch_id: str = ""
    results: list[IntelligenceResult] = field(default_factory=list)
    failed: list[dict[str, Any]] = field(default_factory=list)
    completed_at: datetime = field(default_factory=datetime.utcnow)
