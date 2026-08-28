"""Celery/background task definitions for the clipping engine.

Defines tasks that can be dispatched to a task queue.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def detect_clips_task(video_id: str, channel_id: str, params: dict[str, Any]) -> dict[str, Any]:
    """Background task to detect clips from a video."""
    logger.info("Detecting clips for video %s", video_id)
    return {"video_id": video_id, "status": "completed", "clips_found": 0}


async def render_clip_task(clip_id: str, output_format: str, resolution: str) -> dict[str, Any]:
    """Background task to render a clip."""
    logger.info("Rendering clip %s", clip_id)
    return {"clip_id": clip_id, "status": "completed", "output_url": ""}
