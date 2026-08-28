"""Schemas for AI Clipping Agent — candidates, scores, batch result (Arch. §6)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SegmentInput(BaseModel):
    """One timed transcript/scene segment from upstream production."""

    segment_id: str = ""
    start_seconds: float = 0.0
    end_seconds: float = 0.0
    text: str = ""
    speaker: str = ""
    shot_type: str = ""
    visual_change: float = 0.0  # 0–1 saliency / cut intensity


class AgentRequest(BaseModel):
    topic: str = ""
    video_id: str = ""
    channel_id: str = ""
    # Preferred: explicit timed segments (real upstream handoff)
    segments: list[SegmentInput] = Field(default_factory=list)
    # Fallback inputs used to synthesize segments when timed data absent
    content: dict[str, Any] = Field(default_factory=dict)
    script: dict[str, Any] = Field(default_factory=dict)
    assets: list[dict[str, Any]] = Field(default_factory=list)
    shots: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    min_duration_seconds: float = 15.0
    max_duration_seconds: float = 60.0
    max_clips: int = 5
    score_threshold: float = 0.35
    task_type: str = "select_clips"


class FeatureScores(BaseModel):
    """Arch. §6.3 feature vector for one candidate."""

    hook: float = 0.0  # H(s)
    emotion: float = 0.0  # E(s)
    density: float = 0.0  # D(s)
    narrative: float = 0.0  # N(s)
    context_dependency: float = 0.0  # C(s) — penalty term
    novelty: float = 0.0  # V(s)
    retention: float = 0.0  # R(s)
    quotability: float = 0.0  # Q(s)
    performance_prior: float = 0.0  # P(s)
    duration_penalty: float = 0.0  # T_penalty(s)
    composite: float = 0.0  # ClipScore(s)


class ClipCandidate(BaseModel):
    clip_id: str
    video_id: str = ""
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    text: str = ""
    reconstructed_text: str = ""
    scores: FeatureScores = Field(default_factory=FeatureScores)
    context_complete: bool = False
    rank: int = 0
    rejected_reason: str | None = None


class AgentResponse(BaseModel):
    status: str = "ok"
    video_id: str = ""
    candidates: list[ClipCandidate] = Field(default_factory=list)
    rejected: list[ClipCandidate] = Field(default_factory=list)
    segment_count: int = 0
    result: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    raw_provider_text: str | None = None
    provider_usage: dict[str, Any] | None = None
