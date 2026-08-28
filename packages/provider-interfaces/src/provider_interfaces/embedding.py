"""Embedding provider interface for SentraAura."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class EmbeddingResponse:
    """Response from an embedding provider."""
    vector: list[float]
    model: str = ""
    dimension: int = 0
    latency_ms: float = 0.0
    provider: str = ""
    trace_id: str = ""


class EmbeddingProvider(ABC):
    """Abstract interface for embedding providers."""

    @abstractmethod
    async def embed_text(self, text: str) -> EmbeddingResponse:
        """Generate an embedding for text."""
        ...

    @abstractmethod
    async def embed_image(self, image: bytes) -> EmbeddingResponse:
        """Generate an embedding for an image."""
        ...

    @abstractmethod
    async def search(self, vector: list[float], collection: str, k: int = 10, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Search a vector collection for nearest neighbors."""
        ...

    @abstractmethod
    async def health_check(self) -> tuple[bool, str]:
        """Return (healthy, message) for this provider."""
        ...
