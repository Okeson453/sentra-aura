"""AgentMessage envelope for SentraAura.

Every agent receives and emits this typed envelope so that orchestration,
retries, and audit logging are uniform across the whole agent population.
Matches Architecture §4.1 and contracts/agent-messages/envelope.json.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from agent_contracts.budget import CostBudget


class PriorityLevel(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AgentMessageState(str, Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    STARTED = "STARTED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PAUSED = "PAUSED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    PERMANENT_FAIL = "PERMANENT_FAIL"
    CANCELLED = "CANCELLED"


@dataclass
class AgentMessage:
    """Typed envelope for all agent communication."""

    message_id: UUID = field(default_factory=uuid4)
    correlation_id: UUID = field(default_factory=uuid4)
    parent_workflow_id: UUID | None = None
    agent_type: str = ""
    task_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)
    trace_id: str = ""
    deadline: datetime | None = None
    priority: PriorityLevel = PriorityLevel.NORMAL
    budget: CostBudget = field(default_factory=CostBudget)
    channel_id: str | None = None
    tenant_id: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": str(self.message_id),
            "correlation_id": str(self.correlation_id),
            "parent_workflow_id": str(self.parent_workflow_id) if self.parent_workflow_id else None,
            "agent_type": self.agent_type,
            "task_type": self.task_type,
            "payload": self.payload,
            "state": self.state,
            "trace_id": self.trace_id,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "priority": self.priority.value,
            "budget": self.budget.to_dict(),
            "channel_id": self.channel_id,
            "tenant_id": self.tenant_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentMessage":
        from datetime import datetime as dt
        return cls(
            message_id=UUID(data.get("message_id", str(uuid4()))),
            correlation_id=UUID(data.get("correlation_id", str(uuid4()))),
            parent_workflow_id=UUID(data["parent_workflow_id"]) if data.get("parent_workflow_id") else None,
            agent_type=data.get("agent_type", ""),
            task_type=data.get("task_type", ""),
            payload=data.get("payload", {}),
            state=data.get("state", {}),
            trace_id=data.get("trace_id", ""),
            deadline=dt.fromisoformat(data["deadline"]) if data.get("deadline") else None,
            priority=PriorityLevel(data.get("priority", "NORMAL")),
            budget=CostBudget.from_dict(data.get("budget", {})),
            channel_id=data.get("channel_id"),
            tenant_id=data.get("tenant_id"),
            created_at=dt.fromisoformat(data["created_at"]) if data.get("created_at") else dt.utcnow(),
            updated_at=dt.fromisoformat(data["updated_at"]) if data.get("updated_at") else dt.utcnow(),
        )
