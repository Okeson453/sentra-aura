"""Shot detection pipeline stage.

Detects shot boundaries using TransNetV2 / PySceneDetect / OpenCV.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def detect_shots(
    video_path: str,
    threshold: float = 0.5,
    min_shot_length_seconds: float = 1.0,
) -> dict[str, Any]:
    """Detect shot boundaries in a video.

    Args:
        video_path: Path to the video file.
        threshold: Detection confidence threshold.
        min_shot_length_seconds: Minimum shot duration.

    Returns:
        Dict with shot_boundaries and metadata.
    """
    logger.info("Detecting shots: %s", video_path)
    return {
        "video_path": video_path,
        "threshold": threshold,
        "shot_boundaries": [],
    }
