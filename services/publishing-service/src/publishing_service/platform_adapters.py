"""Platform-specific publishing adapters.

Abstracts platform APIs behind a uniform interface.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class PlatformAdapter:
    """Base class for platform adapters."""

    def __init__(self, platform_id: str) -> None:
        self.platform_id = platform_id

    async def upload(self, asset_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    async def schedule(self, asset_id: str, scheduled_at: str) -> dict[str, Any]:
        raise NotImplementedError

    async def delete(self, platform_content_id: str) -> dict[str, Any]:
        raise NotImplementedError


class YouTubeAdapter(PlatformAdapter):
    """YouTube publishing adapter."""

    def __init__(self) -> None:
        super().__init__("youtube")

    async def upload(self, asset_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
        logger.info("Uploading %s to YouTube", asset_id)
        return {"platform": "youtube", "status": "uploaded", "platform_content_id": f"yt_{asset_id}"}

    async def schedule(self, asset_id: str, scheduled_at: str) -> dict[str, Any]:
        return {"platform": "youtube", "status": "scheduled", "scheduled_at": scheduled_at}

    async def delete(self, platform_content_id: str) -> dict[str, Any]:
        return {"platform": "youtube", "status": "deleted"}


class TikTokAdapter(PlatformAdapter):
    """TikTok publishing adapter."""

    def __init__(self) -> None:
        super().__init__("tiktok")

    async def upload(self, asset_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
        logger.info("Uploading %s to TikTok", asset_id)
        return {"platform": "tiktok", "status": "uploaded", "platform_content_id": f"tt_{asset_id}"}

    async def schedule(self, asset_id: str, scheduled_at: str) -> dict[str, Any]:
        return {"platform": "tiktok", "status": "scheduled", "scheduled_at": scheduled_at}

    async def delete(self, platform_content_id: str) -> dict[str, Any]:
        return {"platform": "tiktok", "status": "deleted"}


def get_adapter(platform_id: str) -> PlatformAdapter:
    """Factory function to get the appropriate platform adapter."""
    adapters = {
        "youtube": YouTubeAdapter(),
        "tiktok": TikTokAdapter(),
    }
    return adapters.get(platform_id, PlatformAdapter(platform_id))
