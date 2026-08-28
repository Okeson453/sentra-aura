"""Codec profiles for video encoding.

Defines platform-optimized encoding profiles for YouTube, TikTok, Instagram, etc.
"""
from __future__ import annotations

from typing import Any


# Platform-optimized codec profiles
CODEC_PROFILES: dict[str, dict[str, Any]] = {
    "youtube_1080p": {
        "name": "YouTube 1080p",
        "resolution": (1920, 1080),
        "video_codec": "libx264",
        "audio_codec": "aac",
        "video_bitrate": "8M",
        "audio_bitrate": "192k",
        "fps": 30,
        "pixel_format": "yuv420p",
        "args": [
            ("-c:v", "libx264"),
            ("-preset", "slow"),
            ("-crf", "18"),
            ("-c:a", "aac"),
            ("-b:a", "192k"),
            ("-pix_fmt", "yuv420p"),
            ("-movflags", "+faststart"),
        ],
    },
    "youtube_shorts_1080p": {
        "name": "YouTube Shorts 1080p",
        "resolution": (1080, 1920),
        "video_codec": "libx264",
        "audio_codec": "aac",
        "video_bitrate": "6M",
        "audio_bitrate": "192k",
        "fps": 30,
        "pixel_format": "yuv420p",
        "args": [
            ("-c:v", "libx264"),
            ("-preset", "slow"),
            ("-crf", "20"),
            ("-c:a", "aac"),
            ("-b:a", "192k"),
            ("-pix_fmt", "yuv420p"),
            ("-movflags", "+faststart"),
        ],
    },
    "tiktok_1080p": {
        "name": "TikTok 1080p",
        "resolution": (1080, 1920),
        "video_codec": "libx264",
        "audio_codec": "aac",
        "video_bitrate": "5M",
        "audio_bitrate": "128k",
        "fps": 30,
        "pixel_format": "yuv420p",
        "args": [
            ("-c:v", "libx264"),
            ("-preset", "medium"),
            ("-crf", "22"),
            ("-c:a", "aac"),
            ("-b:a", "128k"),
            ("-pix_fmt", "yuv420p"),
        ],
    },
    "instagram_reel_1080p": {
        "name": "Instagram Reel 1080p",
        "resolution": (1080, 1920),
        "video_codec": "libx264",
        "audio_codec": "aac",
        "video_bitrate": "5M",
        "audio_bitrate": "128k",
        "fps": 30,
        "pixel_format": "yuv420p",
        "args": [
            ("-c:v", "libx264"),
            ("-preset", "medium"),
            ("-crf", "22"),
            ("-c:a", "aac"),
            ("-b:a", "128k"),
            ("-pix_fmt", "yuv420p"),
        ],
    },
    "proxy_480p": {
        "name": "Proxy 480p",
        "resolution": (854, 480),
        "video_codec": "libx264",
        "audio_codec": "aac",
        "video_bitrate": "1M",
        "audio_bitrate": "96k",
        "fps": 30,
        "pixel_format": "yuv420p",
        "args": [
            ("-c:v", "libx264"),
            ("-preset", "ultrafast"),
            ("-crf", "28"),
            ("-c:a", "aac"),
            ("-b:a", "96k"),
            ("-pix_fmt", "yuv420p"),
        ],
    },
}


def get_profile(name: str) -> dict[str, Any]:
    """Get a codec profile by name."""
    if name not in CODEC_PROFILES:
        raise KeyError(f"Unknown codec profile: {name}")
    return CODEC_PROFILES[name]


def list_profiles() -> list[str]:
    """List all available codec profile names."""
    return list(CODEC_PROFILES.keys())
