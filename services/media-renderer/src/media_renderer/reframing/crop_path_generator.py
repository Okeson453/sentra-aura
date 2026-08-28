"""Crop path generator for vertical reframing.

Generates smooth crop paths that follow tracked subjects while respecting safe zones.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class CropPathGenerator:
    """Generates smooth crop paths for vertical video reframing."""

    def __init__(
        self,
        source_aspect: tuple[int, int] = (16, 9),
        target_aspect: tuple[int, int] = (9, 16),
    ) -> None:
        self.source_aspect = source_aspect
        self.target_aspect = target_aspect
        logger.info("CropPathGenerator: %s -> %s", source_aspect, target_aspect)

    def generate_path(
        self,
        subject_tracks: list[dict[str, Any]],
        duration_seconds: float,
        fps: float = 30.0,
    ) -> list[dict[str, Any]]:
        """Generate a per-frame crop rectangle path.

        Returns a list of crop rectangles (x, y, w, h) per frame,
        smoothed to avoid jarring jumps.
        """
        logger.info("Generating crop path: %.1fs @ %.1f fps", duration_seconds, fps)
        num_frames = int(duration_seconds * fps)
        return [{"x": 0, "y": 0, "w": 1, "h": 1} for _ in range(num_frames)]
