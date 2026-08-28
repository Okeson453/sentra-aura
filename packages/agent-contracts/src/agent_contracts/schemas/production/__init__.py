"""Production domain schemas for SentraAura agents."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class VoiceAsset:
    """Generated TTS narration asset."""
    asset_id: str
    script_id: str
    audio_url: str = ""
    duration_seconds: float = 0.0
    word_timings: list[dict[str, Any]] = field(default_factory=list)
    voice_profile_id: str = ""
    format: str = "mp3"
    status: str = "READY"


@dataclass
class VisualAsset:
    """Generated or sourced visual asset."""
    asset_id: str
    scene_id: str = ""
    asset_type: str = "image"
    url: str = ""
    width: int = 0
    height: int = 0
    format: str = "png"
    provenance: dict[str, Any] = field(default_factory=dict)
    license_type: str = ""
    status: str = "READY"


@dataclass
class LongFormVideo:
    """A rendered long-form video."""
    video_id: str
    channel_id: str
    topic_id: str
    script_id: str = ""
    duration_seconds: int = 0
    resolution: str = "1920x1080"
    status: str = "RENDERING"
    asset_ids: list[str] = field(default_factory=list)
    transcript_id: str = ""
    scene_index_id: str = ""
    render_manifest: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
