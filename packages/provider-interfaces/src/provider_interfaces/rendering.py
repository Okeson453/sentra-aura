"""Rendering provider interface for SentraAura."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EDLConfig:
    """Edit Decision List configuration for rendering."""
    tracks: list[dict[str, Any]] = field(default_factory=list)
    transitions: list[dict[str, Any]] = field(default_factory=list)
    overlays: list[dict[str, Any]] = field(default_factory=list)
    output_resolution: str = "1920x1080"
    output_fps: int = 30
    output_codec: str = "h264"
    output_bitrate: str = "5M"


@dataclass
class RenderResponse:
    """Response from a rendering operation."""
    video_bytes: bytes
    format: str = "mp4"
    duration_seconds: float = 0.0
    width: int = 1920
    height: int = 1080
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    provider: str = ""
    trace_id: str = ""


class RenderingProvider(ABC):
    """Abstract interface for video rendering providers."""

    @abstractmethod
    async def render(self, edl: EDLConfig, assets: dict[str, bytes]) -> RenderResponse:
        """Render a video from an EDL and asset map."""
        ...

    @abstractmethod
    async def health_check(self) -> tuple[bool, str]:
        """Return (healthy, message) for this provider."""
        ...
