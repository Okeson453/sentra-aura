"""Moderation provider interface for SentraAura."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModerationResult:
    """Result of a moderation check."""
    flagged: bool = False
    categories: dict[str, float] = field(default_factory=dict)
    category_scores: dict[str, float] = field(default_factory=dict)
    blocked: bool = False
    reason: str = ""
    latency_ms: float = 0.0
    provider: str = ""
    trace_id: str = ""


class ModerationProvider(ABC):
    """Abstract interface for moderation providers."""

    @abstractmethod
    async def moderate_text(self, text: str) -> ModerationResult:
        """Moderate text content."""
        ...

    @abstractmethod
    async def moderate_image(self, image: bytes) -> ModerationResult:
        """Moderate image content."""
        ...

    @abstractmethod
    async def health_check(self) -> tuple[bool, str]:
        """Return (healthy, message) for this provider."""
        ...
