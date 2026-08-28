"""Pydantic model for script.drafted event."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ScriptDrafted(BaseModel):
    event_id: str
    event_type: str = "script.drafted"
    timestamp: datetime
    channel_id: str
    script_id: str
    topic_id: str
    version: str = "1.0"
    word_count: int | None = None
    scene_count: int | None = None
    hook_variants: list[str] | None = None
    predicted_retention: float | None = Field(None, ge=0.0, le=1.0)
    risk_score: float | None = Field(None, ge=0.0, le=1.0)
    sponsorship_disclosure_required: bool = False
