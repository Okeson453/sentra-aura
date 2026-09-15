"""Shot detection pipeline stage.

Detects shot boundaries. Prefers PySceneDetect / OpenCV when available;
otherwise uses duration-proportional boundaries from ffprobe.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from clipping_engine.pipeline.media_probe import probe_video_meta, segment_windows

logger = logging.getLogger(__name__)


def _try_scenedetect(video_path: str, threshold: float, min_shot: float) -> dict[str, Any] | None:
    try:
        from scenedetect import open_video, SceneManager  # type: ignore
        from scenedetect.detectors import ContentDetector  # type: ignore
    except ImportError:
        return None
    try:
        video = open_video(video_path)
        sm = SceneManager()
        # ContentDetector threshold is typically 27-30; map 0-1 threshold roughly
        sm.add_detector(ContentDetector(threshold=max(10.0, threshold * 40)))
        sm.detect_scenes(video)
        scene_list = sm.get_scene_list()
        boundaries = []
        fps = float(video.frame_rate) if hasattr(video, "frame_rate") else 30.0
        for i, (start, end) in enumerate(scene_list):
            t = start.get_seconds() if hasattr(start, "get_seconds") else float(start)
            if i > 0 and (t - (boundaries[-1]["time"] if boundaries else 0)) < min_shot:
                continue
            boundaries.append({
                "frame": int(t * fps),
                "time": round(t, 3),
                "confidence": 0.85,
            })
        if not boundaries:
            boundaries = [{"frame": 0, "time": 0.0, "confidence": 1.0}]
        return {
            "video_path": video_path,
            "threshold": threshold,
            "min_shot_length_seconds": min_shot,
            "shot_boundaries": boundaries,
            "mode": "pyscenedetect",
        }
    except Exception as exc:
        logger.warning("PySceneDetect failed: %s", exc)
        return None


def detect_shots(
    video_path: str,
    threshold: float = 0.5,
    min_shot_length_seconds: float = 1.0,
) -> dict[str, Any]:
    """Detect shot boundaries in a video."""
    if not Path(video_path).exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    logger.info("Detecting shots: %s", video_path)

    result = _try_scenedetect(video_path, threshold, min_shot_length_seconds)
    if result is not None:
        return result

    meta = probe_video_meta(video_path)
    duration = meta.get("duration_seconds") or 30.0
    fps = meta.get("fps") or 30.0
    # Heuristic: boundary every ~5s, respecting min_shot
    step = max(min_shot_length_seconds, 5.0)
    windows = segment_windows(duration, window_seconds=step)
    boundaries = []
    for start, _end in windows:
        boundaries.append({
            "frame": int(start * fps),
            "time": start,
            "confidence": 0.5,
        })
    return {
        "video_path": video_path,
        "threshold": threshold,
        "min_shot_length_seconds": min_shot_length_seconds,
        "shot_boundaries": boundaries,
        "mode": "heuristic",
        "duration_seconds": duration,
        "warning": "No shot-detection model; duration-proportional boundaries",
    }
