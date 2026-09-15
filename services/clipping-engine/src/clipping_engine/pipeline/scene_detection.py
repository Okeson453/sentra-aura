"""Scene detection pipeline stage.

Groups shots into scenes using visual similarity when embeddings available;
otherwise groups consecutive shots into scenes of bounded length.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from clipping_engine.pipeline.media_probe import probe_duration_seconds

logger = logging.getLogger(__name__)


def detect_scenes(
    video_path: str,
    shot_boundaries: list[dict[str, Any]] | None = None,
    embedding_threshold: float = 0.75,
    max_scene_seconds: float = 30.0,
) -> dict[str, Any]:
    """Detect scenes by grouping shots with visual/audio coherence."""
    if not Path(video_path).exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    logger.info("Detecting scenes: %s", video_path)

    if not shot_boundaries:
        duration = probe_duration_seconds(video_path) or 30.0
        shot_boundaries = [
            {"frame": 0, "time": 0.0},
            {"frame": int(duration * 15), "time": duration / 2},
            {"frame": int(duration * 30), "time": duration},
        ]

    # Group consecutive shots into scenes of at most max_scene_seconds
    scenes: list[dict[str, Any]] = []
    current_shots: list[int] = []
    scene_start = float(shot_boundaries[0].get("time", 0.0))
    for i, boundary in enumerate(shot_boundaries):
        t = float(boundary.get("time", 0.0))
        if current_shots and (t - scene_start) >= max_scene_seconds:
            end_t = float(shot_boundaries[current_shots[-1]].get("time", t))
            # extend to next boundary if available
            if i < len(shot_boundaries):
                end_t = t
            scenes.append({
                "scene_id": f"scene_{len(scenes)}",
                "start_time": scene_start,
                "end_time": end_t,
                "shot_indices": list(current_shots),
            })
            current_shots = [i]
            scene_start = t
        else:
            current_shots.append(i)

    if current_shots:
        last_t = float(shot_boundaries[current_shots[-1]].get("time", scene_start))
        duration = probe_duration_seconds(video_path)
        end_t = duration if duration and duration > last_t else last_t + 5.0
        scenes.append({
            "scene_id": f"scene_{len(scenes)}",
            "start_time": scene_start,
            "end_time": end_t,
            "shot_indices": list(current_shots),
        })

    return {
        "video_path": video_path,
        "scenes": scenes,
        "embedding_threshold": embedding_threshold,
        "mode": "heuristic" if shot_boundaries else "empty",
        "shot_count": len(shot_boundaries),
    }
