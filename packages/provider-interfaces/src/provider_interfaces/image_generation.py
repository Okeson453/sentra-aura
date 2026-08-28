"""Image generation provider interface for SentraAura."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ImageConfig:
    """Configuration for image generation."""
    aspect_ratio: str = "16:9"
    style: str = "photorealistic"
    safety_level: str = "standard"
    seed: int | None = None
    negative_prompt: str = ""
    num_variations: int = 1


@dataclass
class ImageResponse:
    """Response from an image generation provider."""
    image_bytes: bytes
    format: str = "png"
    width: int = 1024
    height: int = 1024
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    provider: str = ""
    trace_id: str = ""
    revised_prompt: str = ""
    nsfw_detected: bool = False


class ImageGenerationProvider(ABC):
    """Abstract interface for image generation providers."""

    @abstractmethod
    async def generate(self, prompt: str, config: ImageConfig | None = None) -> ImageResponse:
        """Generate an image from a text prompt."""
        ...

    @abstractmethod
    async def variations(self, image: bytes, config: ImageConfig | None = None) -> list[ImageResponse]:
        """Generate variations of an existing image."""
        ...

    @abstractmethod
    async def edit(self, image: bytes, mask: bytes | None, prompt: str, config: ImageConfig | None = None) -> ImageResponse:
        """Edit an image with a mask and prompt."""
        ...

    @abstractmethod
    async def health_check(self) -> tuple[bool, str]:
        """Return (healthy, message) for this provider."""
        ...
