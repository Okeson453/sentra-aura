"""Content Asset Graph node models.

Matches Architecture §4.2 and §13.1.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class ContentNodeType(str, Enum):
    TOPIC = "TOPIC"
    SCRIPT = "SCRIPT"
    VIDEO = "VIDEO"
    CLIP = "CLIP"
    THUMBNAIL = "THUMBNAIL"
    METADATA = "METADATA"
    ASSET = "ASSET"
    PUBLICATION = "PUBLICATION"
    PERFORMANCE = "PERFORMANCE"
    EXPERIMENT = "EXPERIMENT"
    POLICY = "POLICY"
    AUDIT_LOG = "AUDIT_LOG"
    DECISION_LOG = "DECISION_LOG"


@dataclass
class ContentNode:
    """A node in the Content Asset Graph."""
    node_id: UUID = field(default_factory=uuid4)
    node_type: ContentNodeType = ContentNodeType.TOPIC
    channel_id: str = ""
    tenant_id: str = ""
    title: str = ""
    description: str = ""
    status: str = "ACTIVE"
    version: int = 1
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    updated_by: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": str(self.node_id),
            "node_type": self.node_type.value,
            "channel_id": self.channel_id,
            "tenant_id": self.tenant_id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "version": self.version,
            "payload": self.payload,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "created_by": self.created_by,
            "updated_by": self.updated_by,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContentNode":
        from datetime import datetime as dt
        return cls(
            node_id=UUID(data.get("node_id", str(uuid4()))),
            node_type=ContentNodeType(data.get("node_type", "TOPIC")),
            channel_id=data.get("channel_id", ""),
            tenant_id=data.get("tenant_id", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            status=data.get("status", "ACTIVE"),
            version=data.get("version", 1),
            payload=data.get("payload", {}),
            created_at=dt.fromisoformat(data["created_at"]) if data.get("created_at") else dt.utcnow(),
            updated_at=dt.fromisoformat(data["updated_at"]) if data.get("updated_at") else dt.utcnow(),
            created_by=data.get("created_by", ""),
            updated_by=data.get("updated_by", ""),
        )
