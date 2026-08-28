"""Agent message envelope for the agent-runtime.

Wraps the canonical AgentMessage from agent-contracts with runtime-specific
metadata: circuit breaker state, retry count, execution timing, and provenance.
Matches Architecture §4.1.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from agent_contracts.envelope import AgentMessage, PriorityLevel
from agent_contracts.budget import CostBudget


class AgentMessagePriority(str, Enum):
    """Runtime priority levels (mirrors canonical envelope)."""
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class AgentMessageEnvelope:
    """Runtime envelope wrapping the canonical AgentMessage.

    Adds execution metadata that is ephemeral and should not be persisted
    in the canonical envelope stored in the content graph.
    """
    message: AgentMessage
    envelope_id: UUID = field(default_factory=uuid4)
    retry_count: int = 0
    circuit_breaker_state: str = "CLOSED"
    execution_start_time: float | None = None
    execution_end_time: float | None = None
    tool_calls_made: list[dict[str, Any]] = field(default_factory=list)
    provider_calls_made: list[dict[str, Any]] = field(default_factory=list)
    cost_accumulated_usd: float = 0.0
    idempotency_key: str = ""
    sandbox_session_id: str | None = None
    injection_scan_result: dict[str, Any] | None = None
    escalation_reason: str | None = None
    checkpoint_data: dict[str, Any] | None = None

    def start_execution(self) -> None:
        """Mark execution start."""
        self.execution_start_time = time.monotonic()
        self.message.state["execution_started_at"] = datetime.utcnow().isoformat()

    def end_execution(self) -> None:
        """Mark execution end and compute duration."""
        self.execution_end_time = time.monotonic()
        duration = self.execution_duration_seconds or 0.0
        self.message.state["execution_completed_at"] = datetime.utcnow().isoformat()
        self.message.state["execution_duration_seconds"] = duration

    @property
    def execution_duration_seconds(self) -> float | None:
        if self.execution_start_time and self.execution_end_time:
            return self.execution_end_time - self.execution_start_time
        return None

    @property
    def is_timed_out(self, timeout_seconds: float = 300.0) -> bool:
        if self.execution_start_time is None:
            return False
        elapsed = time.monotonic() - self.execution_start_time
        return elapsed > timeout_seconds

    def add_tool_call(self, tool_name: str, input_hash: str, output_hash: str, latency_ms: float) -> None:
        self.tool_calls_made.append({
            "tool_name": tool_name,
            "input_hash": input_hash,
            "output_hash": output_hash,
            "latency_ms": latency_ms,
            "timestamp": datetime.utcnow().isoformat(),
        })

    def add_provider_call(self, provider: str, model: str, tokens: int, cost_usd: float, latency_ms: float) -> None:
        self.provider_calls_made.append({
            "provider": provider,
            "model": model,
            "tokens": tokens,
            "cost_usd": cost_usd,
            "latency_ms": latency_ms,
            "timestamp": datetime.utcnow().isoformat(),
        })
        self.cost_accumulated_usd += cost_usd

    def to_dict(self) -> dict[str, Any]:
        return {
            "envelope_id": str(self.envelope_id),
            "message": self.message.to_dict(),
            "retry_count": self.retry_count,
            "circuit_breaker_state": self.circuit_breaker_state,
            "execution_start_time": self.execution_start_time,
            "execution_end_time": self.execution_end_time,
            "tool_calls_made": self.tool_calls_made,
            "provider_calls_made": self.provider_calls_made,
            "cost_accumulated_usd": self.cost_accumulated_usd,
            "idempotency_key": self.idempotency_key,
            "sandbox_session_id": self.sandbox_session_id,
            "injection_scan_result": self.injection_scan_result,
            "escalation_reason": self.escalation_reason,
            "checkpoint_data": self.checkpoint_data,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentMessageEnvelope":
        msg = AgentMessage.from_dict(data["message"])
        return cls(
            message=msg,
            envelope_id=UUID(data.get("envelope_id", str(uuid4()))),
            retry_count=data.get("retry_count", 0),
            circuit_breaker_state=data.get("circuit_breaker_state", "CLOSED"),
            execution_start_time=data.get("execution_start_time"),
            execution_end_time=data.get("execution_end_time"),
            tool_calls_made=data.get("tool_calls_made", []),
            provider_calls_made=data.get("provider_calls_made", []),
            cost_accumulated_usd=data.get("cost_accumulated_usd", 0.0),
            idempotency_key=data.get("idempotency_key", ""),
            sandbox_session_id=data.get("sandbox_session_id"),
            injection_scan_result=data.get("injection_scan_result"),
            escalation_reason=data.get("escalation_reason"),
            checkpoint_data=data.get("checkpoint_data"),
        )
