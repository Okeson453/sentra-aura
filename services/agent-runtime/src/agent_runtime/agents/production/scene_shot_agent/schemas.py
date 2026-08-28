from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field

class Shot(BaseModel):
    shot_id: str
    scene_id: str = ""
    description: str = ""
    duration_seconds: float = 5.0
    visual_asset_id: str | None = None
    camera: str = "medium"

class AgentRequest(BaseModel):
    script: dict[str, Any] = Field(default_factory=dict)
    visual_assets: list[dict[str, Any]] = Field(default_factory=list)
    task_type: str = "plan"

class AgentResponse(BaseModel):
    shots: list[Shot] = Field(default_factory=list)
    edl: list[dict[str, Any]] = Field(default_factory=list)
    raw_provider_text: str | None = None
    provider_usage: dict[str, Any] | None = None
