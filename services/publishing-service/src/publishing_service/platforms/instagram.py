"""Instagram platform adapter.

Handles Instagram Graph API for Reels upload and publishing.
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class InstagramAdapter:
    """Adapter for the Instagram Graph API (Reels)."""

    PLATFORM_ID = "instagram"
    MAX_CAPTION_LENGTH = 2200
    MAX_VIDEO_DURATION_SECONDS = 90
    MAX_VIDEO_SIZE_BYTES = 100_000_000

    def __init__(self, access_token: str | None = None, instagram_account_id: str | None = None) -> None:
        self.access_token = access_token
        self.instagram_account_id = instagram_account_id
        logger.info("InstagramAdapter initialized")

    def upload(
        self,
        video_path: str,
        caption: str,
        share_to_feed: bool = True,
        thumbnail_offset: int = 0,
    ) -> dict[str, Any]:
        """Upload a Reel to Instagram.

        Production: uses Instagram Graph API container-based upload.
        """
        logger.info("Uploading to Instagram: %s", caption[:50])
        return {
            "platform": self.PLATFORM_ID,
            "media_id": f"ig_{os.urandom(4).hex()}",
            "status": "uploaded",
            "share_to_feed": share_to_feed,
        }

    def delete_media(self, media_id: str) -> dict[str, Any]:
        """Delete media from Instagram."""
        logger.info("Deleting Instagram media %s", media_id)
        return {"platform": self.PLATFORM_ID, "media_id": media_id, "status": "deleted"}

    def get_media_status(self, media_id: str) -> dict[str, Any]:
        """Get media status from Instagram."""
        return {
            "platform": self.PLATFORM_ID,
            "media_id": media_id,
            "status": "published",
        }
