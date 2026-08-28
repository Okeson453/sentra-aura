"""Platform capability matrix.

Defines what each publishing platform supports for feature-gating and validation.
"""
from __future__ import annotations

from typing import Any


PLATFORM_CAPABILITIES: dict[str, dict[str, Any]] = {
    "youtube": {
        "upload": True,
        "schedule": True,
        "draft": True,
        "unlisted": True,
        "private": True,
        "public": True,
        "thumbnail_upload": True,
        "chapters": True,
        "end_screens": True,
        "cards": True,
        "monetization": True,
        "shorts": True,
        "live_streaming": True,
        "max_title_length": 100,
        "max_description_length": 5000,
        "max_tags": 500,
        "max_tag_length": 30,
        "max_video_duration_seconds": 43200,
        "max_video_size_bytes": 256_000_000_000,
        "supported_formats": ["mp4", "mov", "avi", "wmv", "flv", "3gpp", "webm"],
        "min_resolution": (1280, 720),
        "aspect_ratios": [(16, 9), (9, 16), (1, 1)],
    },
    "tiktok": {
        "upload": True,
        "schedule": False,
        "draft": True,
        "unlisted": False,
        "private": True,
        "public": True,
        "thumbnail_upload": False,
        "chapters": False,
        "end_screens": False,
        "cards": False,
        "monetization": False,
        "shorts": True,
        "live_streaming": True,
        "max_title_length": 2200,
        "max_description_length": 2200,
        "max_tags": 0,
        "max_tag_length": 0,
        "max_video_duration_seconds": 600,
        "max_video_size_bytes": 287_000_000,
        "supported_formats": ["mp4", "mov"],
        "min_resolution": (540, 960),
        "aspect_ratios": [(9, 16)],
    },
    "instagram": {
        "upload": True,
        "schedule": True,
        "draft": False,
        "unlisted": False,
        "private": False,
        "public": True,
        "thumbnail_upload": False,
        "chapters": False,
        "end_screens": False,
        "cards": False,
        "monetization": False,
        "shorts": True,
        "live_streaming": True,
        "max_title_length": 2200,
        "max_description_length": 2200,
        "max_tags": 30,
        "max_tag_length": 30,
        "max_video_duration_seconds": 90,
        "max_video_size_bytes": 100_000_000,
        "supported_formats": ["mp4", "mov"],
        "min_resolution": (720, 1280),
        "aspect_ratios": [(9, 16), (4, 5), (1, 1)],
    },
}


def supports(platform_id: str, feature: str) -> bool:
    """Check if a platform supports a given feature."""
    return PLATFORM_CAPABILITIES.get(platform_id, {}).get(feature, False)


def get_capability(platform_id: str, feature: str) -> Any:
    """Get a specific capability value for a platform."""
    return PLATFORM_CAPABILITIES.get(platform_id, {}).get(feature)


def validate_asset_for_platform(platform_id: str, asset_metadata: dict[str, Any]) -> list[str]:
    """Validate an asset against platform constraints.

    Returns a list of validation error messages (empty if valid).
    """
    errors: list[str] = []
    caps = PLATFORM_CAPABILITIES.get(platform_id)
    if not caps:
        errors.append(f"Unknown platform: {platform_id}")
        return errors

    title = asset_metadata.get("title", "")
    if len(title) > caps["max_title_length"]:
        errors.append(f"Title exceeds max length ({caps['max_title_length']})")

    desc = asset_metadata.get("description", "")
    if len(desc) > caps["max_description_length"]:
        errors.append(f"Description exceeds max length ({caps['max_description_length']})")

    duration = asset_metadata.get("duration_seconds", 0)
    if duration > caps["max_video_duration_seconds"]:
        errors.append(f"Video duration exceeds max ({caps['max_video_duration_seconds']}s)")

    size = asset_metadata.get("size_bytes", 0)
    if size > caps["max_video_size_bytes"]:
        errors.append(f"Video size exceeds max ({caps['max_video_size_bytes']} bytes)")

    fmt = asset_metadata.get("format", "").lower()
    if fmt not in caps["supported_formats"]:
        errors.append(f"Unsupported format: {fmt}")

    return errors
