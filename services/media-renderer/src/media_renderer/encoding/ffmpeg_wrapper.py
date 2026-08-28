"""FFmpeg wrapper for video encoding.

Provides a typed, fault-tolerant interface to FFmpeg for rendering and transcoding.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class FFmpegWrapper:
    """Typed wrapper around FFmpeg CLI for video operations."""

    def __init__(self, ffmpeg_path: str = "ffmpeg") -> None:
        self.ffmpeg_path = ffmpeg_path
        logger.info("FFmpegWrapper initialized: %s", ffmpeg_path)

    def encode(
        self,
        input_path: str,
        output_path: str,
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        """Encode a video using the specified codec profile.

        Args:
            input_path: Source video path.
            output_path: Destination video path.
            profile: Codec profile dict from codec_profiles.

        Returns:
            Dict with output_path, duration, and metadata.
        """
        cmd = [self.ffmpeg_path, "-y", "-i", input_path]
        for key, value in profile.get("args", []):
            cmd.extend([key, str(value)])
        cmd.append(output_path)

        logger.info("Encoding: %s -> %s", input_path, output_path)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg encode failed: {result.stderr}")

        return {
            "output_path": output_path,
            "profile": profile.get("name", "unknown"),
            "status": "completed",
        }

    def probe(self, video_path: str) -> dict[str, Any]:
        """Probe video metadata using ffprobe."""
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {result.stderr}")
        import json
        return json.loads(result.stdout)
