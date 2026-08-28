"""Agent contracts for the Operations domain.

Defines the interface between the Operations Agent and the orchestrator.
Matches Architecture §5.6 and §14.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class OperationsTaskType(str, Enum):
    SCHEDULING = "SCHEDULING"
    BUDGET_OPTIMIZATION = "BUDGET_OPTIMIZATION"
    RESOURCE_ALLOCATION = "RESOURCE_ALLOCATION"
    COST_ANALYSIS = "COST_ANALYSIS"
    COMPLIANCE_CHECK = "COMPLIANCE_CHECK"
    AUDIT_TRAIL = "AUDIT_TRAIL"


class OperationsStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class OperationsRequest:
    """Request for the Operations Agent."""
    channel_id: str = ""
    tenant_id: str = ""
    task_type: OperationsTaskType = OperationsTaskType.SCHEDULING
    parameters: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    requested_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class OperationsResult:
    """Result from the Operations Agent."""
    result_id: str = ""
    channel_id: str = ""
    task_type: OperationsTaskType = OperationsTaskType.SCHEDULING
    status: OperationsStatus = OperationsStatus.PENDING
    output: dict[str, Any] = field(default_factory=dict)
    cost_estimate: float = 0.0
    resource_usage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None


@dataclass
class OperationsBatchRequest:
    """Batch request for operations tasks."""
    requests: list[OperationsRequest] = field(default_factory=list)
    batch_id: str = ""
    priority: int = 5
    max_parallel: int = 5


@dataclass
class OperationsBatchResult:
    """Batch result for operations tasks."""
    batch_id: str = ""
    results: list[OperationsResult] = field(default_factory=list)
    failed: list[dict[str, Any]] = field(default_factory=list)
    completed_at: datetime = field(default_factory=datetime.utcnow)
