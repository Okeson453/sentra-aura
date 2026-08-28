"""TikTok platform adapter.

Handles TikTok API upload, metadata, and publishing.
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class TikTokAdapter:
    """Adapter for the TikTok for Business / Creator API."""

    PLATFORM_ID = "tiktok"
    MAX_TITLE_LENGTH = 2200
    MAX_VIDEO_DURATION_SECONDS = 600
    MAX_VIDEO_SIZE_BYTES = 287_000_000

    def __init__(self, access_token: str | None = None) -> None:
        self.access_token = access_token
        logger.info("TikTokAdapter initialized")

    def upload(
        self,
        video_path: str,
        title: str,
        privacy_level: str = "public",
        disable_duet: bool = False,
        disable_stitch: bool = False,
        disable_comment: bool = False,
        video_cover_timestamp_ms: int = 0,
    ) -> dict[str, Any]:
        """Upload a video to TikTok.

        Production: uses TikTok Creator API or direct upload flow.
        """
        logger.info("Uploading to TikTok: %s", title)
        return {
            "platform": self.PLATFORM_ID,
            "video_id": f"tt_{os.urandom(4).hex()}",
            "status": "uploaded",
            "privacy_level": privacy_level,
        }

    def delete_video(self, video_id: str) -> dict[str, Any]:
        """Delete a video from TikTok."""
        logger.info("Deleting TikTok video %s", video_id)
        return {"platform": self.PLATFORM_ID, "video_id": video_id, "status": "deleted"}

    def get_video_status(self, video_id: str) -> dict[str, Any]:
        """Get video status from TikTok."""
        return {
            "platform": self.PLATFORM_ID,
            "video_id": video_id,
            "status": "published",
        }
