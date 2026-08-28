"""Agent contracts for the Production domain.

Defines the interface between the Production Agent and the orchestrator.
Matches Architecture §5.2 and §14.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ProductionAssetType(str, Enum):
    VIDEO = "VIDEO"
    AUDIO = "AUDIO"
    IMAGE = "IMAGE"
    ANIMATION = "ANIMATION"
    COMPOSITE = "COMPOSITE"


class ProductionStatus(str, Enum):
    QUEUED = "QUEUED"
    RENDERING = "RENDERING"
    REVIEW = "REVIEW"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class ProductionRequest:
    """Request for the Production Agent to render media."""
    script_id: str = ""
    channel_id: str = ""
    tenant_id: str = ""
    asset_type: ProductionAssetType = ProductionAssetType.VIDEO
    resolution: str = "1080p"
    fps: int = 30
    duration_seconds: float = 0.0
    assets: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    requested_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ProductionResult:
    """Result from the Production Agent."""
    asset_id: str = ""
    script_id: str = ""
    channel_id: str = ""
    asset_type: ProductionAssetType = ProductionAssetType.VIDEO
    status: ProductionStatus = ProductionStatus.QUEUED
    resolution: str = "1080p"
    fps: int = 30
    duration_seconds: float = 0.0
    file_size_bytes: int = 0
    storage_path: str = ""
    storage_provider: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None


@dataclass
class ProductionBatchRequest:
    """Batch request for production."""
    requests: list[ProductionRequest] = field(default_factory=list)
    batch_id: str = ""
    priority: int = 5
    max_parallel: int = 2


@dataclass
class ProductionBatchResult:
    """Batch result for production."""
    batch_id: str = ""
    results: list[ProductionResult] = field(default_factory=list)
    failed: list[dict[str, Any]] = field(default_factory=list)
    completed_at: datetime = field(default_factory=datetime.utcnow)
