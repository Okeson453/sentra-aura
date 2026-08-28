"""Audio extraction pipeline stage.

Extracts WAV 48kHz mono audio from video files for downstream ASR and analysis.
"""
from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def extract_audio(
    video_path: str,
    output_path: str | None = None,
    sample_rate: int = 48000,
    channels: int = 1,
) -> dict[str, Any]:
    """Extract audio from a video file using FFmpeg.

    Args:
        video_path: Path to the source video file.
        output_path: Optional output path; auto-generated if None.
        sample_rate: Target sample rate in Hz.
        channels: Number of audio channels.

    Returns:
        Dict with output_path, duration_seconds, and metadata.
    """
    video = Path(video_path)
    if not video.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    if output_path is None:
        output_path = str(video.with_suffix(".wav"))

    cmd = [
        "ffmpeg", "-y", "-i", str(video),
        "-vn", "-acodec", "pcm_s16le",
        "-ar", str(sample_rate), "-ac", str(channels),
        output_path,
    ]
    logger.info("Extracting audio: %s -> %s", video_path, output_path)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg audio extraction failed: {result.stderr}")

    # Probe duration
    probe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", output_path]
    probe = subprocess.run(probe_cmd, capture_output=True, text=True)
    duration = float(probe.stdout.strip()) if probe.returncode == 0 else 0.0

    return {
        "output_path": output_path,
        "duration_seconds": duration,
        "sample_rate": sample_rate,
        "channels": channels,
        "source_video": video_path,
    }
