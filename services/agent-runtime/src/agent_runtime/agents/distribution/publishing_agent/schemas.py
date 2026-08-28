from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field

class AgentRequest(BaseModel):
    topic: str = ""
    content: dict[str, Any] = Field(default_factory=dict)
    script: dict[str, Any] = Field(default_factory=dict)
    assets: list[dict[str, Any]] = Field(default_factory=list)
    shots: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    task_type: str = "run"

class AgentResponse(BaseModel):
    status: str = "ok"
    result: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    raw_provider_text: str | None = None
    provider_usage: dict[str, Any] | None = None
