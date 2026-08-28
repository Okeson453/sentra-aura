"""Models for the Data Ingestion Pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4


@dataclass
class RawEvent:
    """A raw event from a data source."""
    event_id: str = field(default_factory=lambda: str(uuid4())[:32])
    source: str = ""
    source_type: str = ""
    raw_payload: dict[str, Any] = field(default_factory=dict)
    collected_at: datetime = field(default_factory=datetime.utcnow)
    channel_id: str | None = None
    tenant_id: str | None = None


@dataclass
class NormalizedEvent:
    """A normalized event ready for downstream consumption."""
    event_id: str = ""
    source: str = ""
    event_type: str = ""
    channel_id: str | None = None
    tenant_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    normalized_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IngestionJob:
    """An ingestion job."""
    job_id: str = field(default_factory=lambda: str(uuid4())[:32])
    source: str = ""
    status: str = "PENDING"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    events_collected: int = 0
    events_normalized: int = 0
    errors: list[str] = field(default_factory=list)
