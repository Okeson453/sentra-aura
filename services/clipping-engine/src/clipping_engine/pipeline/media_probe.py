"""Shared media probing helpers for clipping pipeline stages.

Uses ffprobe when available; falls back to safe defaults. Never invents
file content — duration and stream info are derived from the actual file
or reported as unavailable.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def probe_duration_seconds(path: str) -> float | None:
    """Return media duration in seconds, or None if unprobeable."""
    p = Path(path)
    if not p.exists():
        return None
    if not shutil.which("ffprobe"):
        logger.debug("ffprobe not available; cannot probe duration for %s", path)
        return None
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(p),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError, OSError) as exc:
        logger.warning("ffprobe failed for %s: %s", path, exc)
    return None


def probe_video_meta(path: str) -> dict[str, Any]:
    """Probe basic video metadata (duration, fps, frames) via ffprobe."""
    meta: dict[str, Any] = {
        "path": path,
        "exists": Path(path).exists(),
        "duration_seconds": None,
        "fps": None,
        "width": None,
        "height": None,
        "probe_backend": "none",
    }
    if not meta["exists"]:
        return meta
    if not shutil.which("ffprobe"):
        return meta
    # Duration
    dur = probe_duration_seconds(path)
    meta["duration_seconds"] = dur
    # Stream info
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,nb_frames",
        "-of", "csv=p=0",
        path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(",")
            if len(parts) >= 2:
                try:
                    meta["width"] = int(parts[0]) if parts[0] else None
                    meta["height"] = int(parts[1]) if parts[1] else None
                except ValueError:
                    pass
            if len(parts) >= 3 and parts[2] and "/" in parts[2]:
                num, den = parts[2].split("/", 1)
                try:
                    meta["fps"] = float(num) / max(float(den), 1e-9)
                except ValueError:
                    pass
            meta["probe_backend"] = "ffprobe"
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("ffprobe stream probe failed for %s: %s", path, exc)
    return meta


def segment_windows(
    duration_seconds: float,
    window_seconds: float = 5.0,
    max_segments: int = 64,
) -> list[tuple[float, float]]:
    """Split a duration into contiguous windows for heuristic segmentation."""
    if duration_seconds <= 0:
        return [(0.0, window_seconds)]
    windows: list[tuple[float, float]] = []
    t = 0.0
    while t < duration_seconds and len(windows) < max_segments:
        end = min(t + window_seconds, duration_seconds)
        windows.append((round(t, 3), round(end, 3)))
        t = end
        if end >= duration_seconds:
            break
    return windows
