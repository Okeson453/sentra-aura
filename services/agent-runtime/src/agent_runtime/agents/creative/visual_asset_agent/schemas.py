from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field

class VisualAsset(BaseModel):
    asset_id: str
    scene_id: str = ""
    prompt: str = ""
    image_url: str | None = None
    source: str = "generated"  # generated | stock | edited
    provenance: dict[str, Any] = Field(default_factory=dict)
    brand_compliant: bool = True

class VisualAssetRequest(BaseModel):
    scene_descriptions: list[str] = Field(default_factory=list)
    script: dict[str, Any] = Field(default_factory=dict)  # scripting handoff
    asset_budget: int = 5
    brand_style: str = ""
    task_type: str = "generate"

class VisualAssetResponse(BaseModel):
    assets: list[VisualAsset] = Field(default_factory=list)
    manifest: dict[str, Any] = Field(default_factory=dict)
    rejected_count: int = 0
    raw_provider_text: str | None = None
    provider_usage: dict[str, Any] | None = None
