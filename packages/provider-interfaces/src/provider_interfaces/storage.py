"""Storage provider interface for SentraAura."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class StorageResponse:
    """Response from a storage operation."""
    url: str = ""
    path: str = ""
    etag: str = ""
    size_bytes: int = 0
    content_type: str = ""
    latency_ms: float = 0.0
    provider: str = ""
    trace_id: str = ""


class StorageProvider(ABC):
    """Abstract interface for object storage providers."""

    @abstractmethod
    async def put(self, path: str, data: bytes, content_type: str = "application/octet-stream", metadata: dict[str, str] | None = None) -> StorageResponse:
        """Store data at the given path."""
        ...

    @abstractmethod
    async def get(self, path: str) -> bytes:
        """Retrieve data from the given path."""
        ...

    @abstractmethod
    async def delete(self, path: str) -> bool:
        """Delete data at the given path."""
        ...

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check if data exists at the given path."""
        ...

    @abstractmethod
    async def presigned_url(self, path: str, expiry_seconds: int = 3600, operation: str = "get") -> str:
        """Generate a presigned URL for the given path."""
        ...

    @abstractmethod
    async def list_objects(self, prefix: str, max_keys: int = 1000) -> list[StorageResponse]:
        """List objects under the given prefix."""
        ...

    @abstractmethod
    async def health_check(self) -> tuple[bool, str]:
        """Return (healthy, message) for this provider."""
        ...
