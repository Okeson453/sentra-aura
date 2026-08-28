"""Publishing Service background worker.

Processes publishing tasks from the queue: validate, upload, monitor, retry.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class PublishingWorker:
    """Background worker for publishing operations."""

    def __init__(self, platform_adapters: dict[str, Any] | None = None) -> None:
        self.platform_adapters = platform_adapters or {}
        logger.info("PublishingWorker initialized")

    def process_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """Process a single publishing task."""
        platform_id = task.get("platform_id")
        asset_id = task.get("asset_id")
        logger.info("Processing publish task: %s -> %s", asset_id, platform_id)

        adapter = self.platform_adapters.get(platform_id)
        if not adapter:
            return {
                "success": False,
                "error_code": "UNKNOWN_PLATFORM",
                "error_message": f"No adapter for platform: {platform_id}",
            }

        try:
            result = adapter.upload(
                video_path=task.get("video_path", ""),
                title=task.get("title", ""),
                description=task.get("description", ""),
                tags=task.get("tags"),
                privacy_status=task.get("privacy_status", "private"),
                scheduled_at=task.get("scheduled_at"),
                thumbnail_path=task.get("thumbnail_path"),
            )
            return {"success": True, **result}
        except Exception as exc:
            logger.exception("Publishing failed for %s", asset_id)
            return {
                "success": False,
                "error_code": "PUBLISH_FAILED",
                "error_message": str(exc),
            }

    def run(self) -> None:
        """Main worker loop. Production: integrates with Celery / RQ."""
        logger.info("PublishingWorker run loop started")
