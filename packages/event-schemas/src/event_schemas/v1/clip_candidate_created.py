"""Pydantic model for clip.candidate.created event."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ClipCandidate(BaseModel):
    candidate_id: str
    start_ms: int
    end_ms: int
    clip_type: str = Field(..., pattern=r"^(HOOK|QUOTE|HIGHLIGHT|EDUCATIONAL|STORY|SERIES|COMPILATION)$")
    clip_score: float = Field(..., ge=0.0, le=1.0)
    context_score: float | None = Field(None, ge=0.0, le=1.0)
    hook_score: float | None = Field(None, ge=0.0, le=1.0)
    retention_prediction: float | None = Field(None, ge=0.0, le=1.0)
    compliance_risk: float | None = Field(None, ge=0.0, le=1.0)


class ClipCandidateCreated(BaseModel):
    event_id: str
    event_type: str = "clip.candidate.created"
    timestamp: datetime
    channel_id: str
    source_video_id: str
    clip_candidates: list[ClipCandidate]
