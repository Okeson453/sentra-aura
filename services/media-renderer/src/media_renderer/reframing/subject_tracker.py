"""Subject tracker for vertical reframing.

Tracks primary subjects (faces, objects) across frames for smart crop path generation.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class SubjectTracker:
    """Tracks primary subjects across video frames."""

    def __init__(self, model_name: str = "yolov8-face") -> None:
        self.model_name = model_name
        self._model: Any = None
        logger.info("SubjectTracker initialized: %s", model_name)

    def track(self, video_path: str) -> list[dict[str, Any]]:
        """Track subjects across all frames of a video.

        Returns a list of per-frame bounding boxes with subject IDs.
        """
        logger.info("Tracking subjects: %s", video_path)
        return []

    def get_primary_subject(self, frame_index: int) -> dict[str, Any] | None:
        """Get the primary subject for a given frame."""
        return None
