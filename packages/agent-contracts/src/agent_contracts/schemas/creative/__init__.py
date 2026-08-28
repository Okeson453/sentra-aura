"""Creative domain schemas for SentraAura agents."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ResearchBundle:
    """Validated research corpus for a topic."""
    bundle_id: str
    topic_id: str
    sources: list[str] = field(default_factory=list)
    claims: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    coverage_score: float = 0.0
    confidence_score: float = 0.0
    status: str = "PENDING"
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ContentStrategy:
    """Content strategy for a channel/topic."""
    strategy_id: str
    channel_id: str
    topic: str
    format: str = "longform"
    angle: str = ""
    hook_candidates: list[str] = field(default_factory=list)
    target_audience: str = ""
    tone: str = ""
    estimated_duration: int = 600


@dataclass
class Script:
    """A drafted script with scene breakdown."""
    script_id: str
    topic_id: str
    title: str = ""
    content: str = ""
    scenes: list[dict[str, Any]] = field(default_factory=list)
    hook_variants: list[str] = field(default_factory=list)
    visual_direction: list[str] = field(default_factory=list)
    word_count: int = 0
    estimated_duration: int = 0
    disclosure_tags: list[str] = field(default_factory=list)
    status: str = "DRAFT"
    version: int = 1
    created_at: datetime = field(default_factory=datetime.utcnow)
