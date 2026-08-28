"""Content Asset Graph edge models."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class ContentEdgeType(str, Enum):
    DRAFTED_FROM = "DRAFTED_FROM"
    RENDERED_FROM = "RENDERED_FROM"
    CLIPPED_FROM = "CLIPPED_FROM"
    THUMBNAIL_FOR = "THUMBNAIL_FOR"
    METADATA_FOR = "METADATA_FOR"
    PUBLISHED_AS = "PUBLISHED_AS"
    PERFORMANCE_OF = "PERFORMANCE_OF"
    DERIVED_FROM = "DERIVED_FROM"
    EXPERIMENT_ON = "EXPERIMENT_ON"
    POLICY_FOR = "POLICY_FOR"
    AUDIT_OF = "AUDIT_OF"


@dataclass
class ContentEdge:
    """An edge in the Content Asset Graph."""
    edge_id: UUID = field(default_factory=uuid4)
    source_id: UUID = field(default_factory=uuid4)
    target_id: UUID = field(default_factory=uuid4)
    edge_type: ContentEdgeType = ContentEdgeType.DERIVED_FROM
    channel_id: str = ""
    tenant_id: str = ""
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": str(self.edge_id),
            "source_id": str(self.source_id),
            "target_id": str(self.target_id),
            "edge_type": self.edge_type.value,
            "channel_id": self.channel_id,
            "tenant_id": self.tenant_id,
            "weight": self.weight,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContentEdge":
        from datetime import datetime as dt
        return cls(
            edge_id=UUID(data.get("edge_id", str(uuid4()))),
            source_id=UUID(data["source_id"]) if data.get("source_id") else uuid4(),
            target_id=UUID(data["target_id"]) if data.get("target_id") else uuid4(),
            edge_type=ContentEdgeType(data.get("edge_type", "DERIVED_FROM")),
            channel_id=data.get("channel_id", ""),
            tenant_id=data.get("tenant_id", ""),
            weight=data.get("weight", 1.0),
            metadata=data.get("metadata", {}),
            created_at=dt.fromisoformat(data["created_at"]) if data.get("created_at") else dt.utcnow(),
        )
