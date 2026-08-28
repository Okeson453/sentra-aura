"""Celery/background task definitions for the media renderer.

Defines tasks that can be dispatched to a task queue.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def render_task(project_id: str, output_format: str, resolution: str) -> dict[str, Any]:
    """Background task to render a media project."""
    logger.info("Rendering project %s", project_id)
    return {"project_id": project_id, "status": "completed", "output_url": ""}


async def transcode_task(asset_id: str, target_format: str) -> dict[str, Any]:
    """Background task to transcode an asset."""
    logger.info("Transcoding asset %s", asset_id)
    return {"asset_id": asset_id, "status": "completed", "output_url": ""}
