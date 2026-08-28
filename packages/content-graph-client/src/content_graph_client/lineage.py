"""Content Asset Graph lineage record models."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class LineageRecordType(str, Enum):
    SOURCE = "SOURCE"
    TRANSFORM = "TRANSFORM"
    AGENT = "AGENT"
    HUMAN = "HUMAN"
    TOOL = "TOOL"
    DECISION = "DECISION"
    FEEDBACK = "FEEDBACK"


@dataclass
class LineageRecord:
    """An immutable lineage record in the Content Asset Graph."""
    record_id: UUID = field(default_factory=uuid4)
    node_id: UUID = field(default_factory=uuid4)
    record_type: LineageRecordType = LineageRecordType.SOURCE
    agent_id: str = ""
    action: str = ""
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": str(self.record_id),
            "node_id": str(self.node_id),
            "record_type": self.record_type.value,
            "agent_id": self.agent_id,
            "action": self.action,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LineageRecord":
        from datetime import datetime as dt
        return cls(
            record_id=UUID(data.get("record_id", str(uuid4()))),
            node_id=UUID(data["node_id"]) if data.get("node_id") else uuid4(),
            record_type=LineageRecordType(data.get("record_type", "SOURCE")),
            agent_id=data.get("agent_id", ""),
            action=data.get("action", ""),
            inputs=data.get("inputs", {}),
            outputs=data.get("outputs", {}),
            metadata=data.get("metadata", {}),
            created_at=dt.fromisoformat(data["created_at"]) if data.get("created_at") else dt.utcnow(),
        )
