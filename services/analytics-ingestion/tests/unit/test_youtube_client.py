"""Unit tests for YouTube Analytics client."""
from __future__ import annotations

import pytest
from datetime import datetime

from analytics_ingestion.youtube_analytics_client import YouTubeAnalyticsClient, VideoMetrics


@pytest.mark.asyncio
async def test_client_initialization():
    client = YouTubeAnalyticsClient(api_key="test-key")
    assert client.api_key == "test-key"
    assert client.base_url == "https://www.googleapis.com/youtube/v3"
    await client.close()


@pytest.mark.asyncio
async def test_client_custom_base_url():
    client = YouTubeAnalyticsClient(api_key="test-key", base_url="https://custom.api.com")
    assert client.base_url == "https://custom.api.com"
    await client.close()


def test_video_metrics_dataclass():
    metrics = VideoMetrics(
        video_id="vid-123",
        channel_id="ch-456",
        views=10000,
        likes=500,
        comments=100,
        shares=50,
        watch_time_seconds=800000,
        average_view_duration_seconds=240.0,
        ctr=0.08,
        retention_curve=[1.0, 0.9, 0.8, 0.7, 0.6],
        subscriber_gain=89,
        measured_at=datetime.utcnow(),
    )
    assert metrics.video_id == "vid-123"
    assert metrics.views == 10000
    assert len(metrics.retention_curve) == 5
