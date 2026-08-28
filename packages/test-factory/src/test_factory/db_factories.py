"""Database factories for SentraAura tests."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class ChannelFactory:
    """Factory for creating Channel test data."""

    _counter = 0

    @classmethod
    def build(cls, **overrides: Any) -> dict[str, Any]:
        cls._counter += 1
        return {
            "channel_id": f"CH-{cls._counter:04d}",
            "name": f"Test Channel {cls._counter}",
            "description": "A test channel",
            "status": "active",
            "autonomy_level": "L2",
            "brand_policy": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            **overrides,
        }


class ScriptFactory:
    """Factory for creating Script test data."""

    _counter = 0

    @classmethod
    def build(cls, **overrides: Any) -> dict[str, Any]:
        cls._counter += 1
        return {
            "script_id": f"SCR-{cls._counter:04d}",
            "topic_id": f"TOP-{cls._counter:04d}",
            "channel_id": f"CH-{cls._counter:04d}",
            "version": "1.0",
            "word_count": 1500,
            "scene_count": 8,
            "hook_variants": ["Hook A", "Hook B"],
            "predicted_retention": 0.75,
            "risk_score": 0.2,
            "sponsorship_disclosure_required": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            **overrides,
        }


class VideoFactory:
    """Factory for creating Video test data."""

    _counter = 0

    @classmethod
    def build(cls, **overrides: Any) -> dict[str, Any]:
        cls._counter += 1
        return {
            "video_id": f"VID-{cls._counter:04d}",
            "script_id": f"SCR-{cls._counter:04d}",
            "channel_id": f"CH-{cls._counter:04d}",
            "duration_seconds": 600,
            "resolution": "1920x1080",
            "file_size_mb": 150.0,
            "render_time_seconds": 300,
            "qc_status": "passed",
            **overrides,
        }
