"""Clipping domain schemas for SentraAura agents."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Segment:
    """A semantic segment from a long-form video."""
    segment_id: str
    video_id: str
    start_ms: int = 0
    end_ms: int = 0
    semantic_type: str = ""
    entities: list[str] = field(default_factory=list)
    emotion_score: float = 0.0
    novelty_score: float = 0.0
    hook_potential: float = 0.0
    completion_potential: float = 0.0
    information_density: float = 0.0
    embedding_id: str = ""


@dataclass
class ClipCandidate:
    """A scored clip candidate."""
    candidate_id: str
    source_video_id: str
    segment_ids: list[str] = field(default_factory=list)
    clip_type: str = "HIGHLIGHT"
    start_ms: int = 0
    end_ms: int = 0
    duration_ms: int = 0
    aspect_ratio: str = "9:16"
    context_score: float = 0.0
    hook_score: float = 0.0
    retention_prediction: float = 0.0
    clip_value: float = 0.0
    status: str = "CANDIDATE"
    lineage: dict[str, Any] = field(default_factory=dict)


@dataclass
class Clip:
    """A finalized clip ready for publishing."""
    clip_id: str
    source_video_id: str
    clip_type: str = ""
    original_start_ms: int = 0
    original_end_ms: int = 0
    local_duration_ms: int = 0
    aspect_ratio: str = "9:16"
    context_score: float = 0.0
    hook_score: float = 0.0
    retention_prediction: float = 0.0
    status: str = "READY_TO_PUBLISH"
    lineage: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
