"""Publishing provider interface for SentraAura."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class PublicationMetadata:
    """Metadata for a platform publication."""
    title: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    category: str = ""
    privacy: str = "public"
    scheduled_at: datetime | None = None
    playlist_ids: list[str] = field(default_factory=list)
    thumbnail_path: str = ""
    disclosure_flags: list[str] = field(default_factory=list)
    language: str = "en"
    made_for_kids: bool = False


@dataclass
class PublishResponse:
    """Response from a publishing operation."""
    platform_id: str = ""
    platform_url: str = ""
    status: str = "published"
    published_at: datetime | None = None
    scheduled_at: datetime | None = None
    latency_ms: float = 0.0
    provider: str = ""
    trace_id: str = ""
    raw_response: dict[str, Any] = field(default_factory=dict)


class PublishProvider(ABC):
    """Abstract interface for platform publishing providers."""

    @abstractmethod
    async def upload(self, video: bytes, metadata: PublicationMetadata) -> PublishResponse:
        """Upload a video to the platform."""
        ...

    @abstractmethod
    async def update(self, platform_id: str, metadata: PublicationMetadata) -> PublishResponse:
        """Update metadata for an existing publication."""
        ...

    @abstractmethod
    async def delete(self, platform_id: str) -> bool:
        """Delete a publication from the platform."""
        ...

    @abstractmethod
    async def get_status(self, platform_id: str) -> dict[str, Any]:
        """Get the current status of a publication."""
        ...

    @abstractmethod
    async def health_check(self) -> tuple[bool, str]:
        """Return (healthy, message) for this provider."""
        ...
