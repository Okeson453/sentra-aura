"""Content Asset Graph edge models."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class ContentEdgeType(str, Enum):
    DRAFTED_FROM = "DRAFTED_FROM"
    RENDERED_FROM = "RENDERED_FROM"
    CLIPPED_FROM = "CLIPPED_FROM"
    THUMBNAIL_FOR = "THUMBNAIL_FOR"
    PUBLISHED_AS = "PUBLISHED_AS"
    OPTIMIZED_BY = "OPTIMIZED_BY"
    MEASURED_BY = "MEASURED_BY"
    AB_TESTED_WITH = "AB_TESTED_WITH"
    DERIVED_FROM = "DERIVED_FROM"


@dataclass
class ContentEdge:
    """Directed edge in the Content Asset Graph (Architecture §5 / §57)."""

    edge_id: UUID = field(default_factory=uuid4)
    source_id: UUID = field(default_factory=uuid4)
    target_id: UUID = field(default_factory=uuid4)
    edge_type: ContentEdgeType | str = ContentEdgeType.DERIVED_FROM
    channel_id: str = ""
    tenant_id: str = ""
    weight: float = 1.0
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    superseded_by: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": str(self.edge_id),
            "source_id": str(self.source_id),
            "target_id": str(self.target_id),
            "edge_type": self.edge_type.value if isinstance(self.edge_type, Enum) else str(self.edge_type),
            "channel_id": self.channel_id,
            "tenant_id": self.tenant_id,
            "weight": self.weight,
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_to": self.valid_to.isoformat() if self.valid_to else None,
            "superseded_by": self.superseded_by,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }
