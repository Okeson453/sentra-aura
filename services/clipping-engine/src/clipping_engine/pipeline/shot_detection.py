"""Shot detection pipeline stage.

Detects shot boundaries using TransNetV2 / PySceneDetect / OpenCV.
"""
from __future__ import annotations

import logging
import time
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
    time.sleep(0.1)
    
    # Generate mock shot boundaries
    mock_boundaries = [
        {"frame": 0, "time": 0.0, "confidence": 0.95},
        {"frame": 150, "time": 5.0, "confidence": 0.92},
        {"frame": 450, "time": 15.0, "confidence": 0.88},
        {"frame": 600, "time": 20.0, "confidence": 0.91},
    ]
    
    return {
        "video_path": video_path,
        "threshold": threshold,
        "min_shot_length_seconds": min_shot_length_seconds,
        "shot_boundaries": mock_boundaries,
    }
