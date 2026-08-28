"""Video generation provider interface for SentraAura."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class VideoConfig:
    """Configuration for video generation."""
    duration_seconds: float = 5.0
    resolution: str = "1080p"
    fps: int = 24
    style: str = "cinematic"
    seed: int | None = None


@dataclass
class VideoResponse:
    """Response from a video generation provider."""
    video_bytes: bytes
    format: str = "mp4"
    duration_seconds: float = 0.0
    width: int = 1920
    height: int = 1080
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    provider: str = ""
    trace_id: str = ""


class VideoGenerationProvider(ABC):
    """Abstract interface for video generation providers."""

    @abstractmethod
    async def generate(self, prompt: str, config: VideoConfig | None = None) -> VideoResponse:
        """Generate a video from a text prompt."""
        ...

    @abstractmethod
    async def extend(self, video: bytes, duration_seconds: float, config: VideoConfig | None = None) -> VideoResponse:
        """Extend an existing video by the specified duration."""
        ...

    @abstractmethod
    async def health_check(self) -> tuple[bool, str]:
        """Return (healthy, message) for this provider."""
        ...
