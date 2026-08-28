"""Timeline builder for media assembly.

Constructs edit decision lists (EDLs) and timelines from clips, audio, and visuals.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class TimelineBuilder:
    """Builds video timelines from ordered clip segments."""

    def __init__(self, resolution: tuple[int, int] = (1920, 1080), fps: float = 30.0) -> None:
        self.resolution = resolution
        self.fps = fps
        self.tracks: dict[str, list[dict[str, Any]]] = {}
        logger.info("TimelineBuilder initialized: %s @ %.1f fps", resolution, fps)

    def add_clip(
        self,
        track: str,
        source_path: str,
        start_time: float,
        end_time: float,
        position: tuple[float, float] = (0.0, 0.0),
        scale: tuple[float, float] = (1.0, 1.0),
    ) -> None:
        """Add a clip to a timeline track."""
        if track not in self.tracks:
            self.tracks[track] = []
        self.tracks[track].append({
            "source_path": source_path,
            "start_time": start_time,
            "end_time": end_time,
            "position": position,
            "scale": scale,
        })
        logger.info("Added clip to track '%s': %s [%.2f-%.2f]", track, source_path, start_time, end_time)

    def build_edl(self) -> dict[str, Any]:
        """Build and return the edit decision list."""
        return {
            "resolution": self.resolution,
            "fps": self.fps,
            "tracks": self.tracks,
        }
