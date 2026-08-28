"""Pydantic models for the Agent Registry Service."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AgentType(str, Enum):
    """Legacy classification used by older registry tests and clients."""
    SCRIPT_WRITER = "script_writer"
    RESEARCHER = "researcher"
    PRODUCER = "producer"
    EDITOR = "editor"
    PUBLISHER = "publisher"
    ANALYST = "analyst"
    ORCHESTRATOR = "orchestrator"
    GENERIC = "generic"


class AgentStatus(str, Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    EXPERIMENTAL = "experimental"
    DISABLED = "disabled"


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class EvaluationStatus(str, Enum):
    CANARY = "canary"
    STAGING = "staging"
    PRODUCTION = "production"
    DEPRECATED = "deprecated"


class AgentRegistration(BaseModel):
    agent_id: str
    name: str
    domain: str = "general"
    agent_type: AgentType | str = AgentType.GENERIC
    version: str = "1.0.0"
    description: str = ""
    capabilities: list[str] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    required_permissions: list[str] = Field(default_factory=list)
    endpoint: str = ""
    autonomy_level: str = "L2"
    risk_tier: str = "medium"
    cost_estimate_usd: float = 0.0
    avg_latency_ms: float = 0.0
    status: AgentStatus = AgentStatus.ACTIVE
    registered_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RegisteredAgent(BaseModel):
    agent_id: str
    name: str
    domain: str
    version: str
    status: AgentStatus
    description: str = ""
    capabilities: list[str] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    cost_estimate_usd: float = 0.0
    avg_latency_ms: float = 0.0
    registered_at: datetime
    health: HealthStatus = HealthStatus.UNKNOWN


class AgentVersion(BaseModel):
    version: str
    status: AgentStatus
    release_notes: str = ""
    released_at: datetime = Field(default_factory=datetime.utcnow)
    deprecated_at: datetime | None = None


class AgentHealth(BaseModel):
    agent_id: str
    status: HealthStatus
    last_heartbeat: datetime | None = None
    success_rate: float = 0.0
    avg_latency_ms: float = 0.0
    error_count_24h: int = 0
    invocation_count_24h: int = 0


class EvaluationRecord(BaseModel):
    evaluation_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    status: EvaluationStatus
    score: float = Field(ge=0.0, le=1.0)
    evaluator: str
    notes: str = ""
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)
    metrics: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = "1.0.0"
    checks: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    trace_id: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
