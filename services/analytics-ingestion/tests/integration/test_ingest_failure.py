"""Regression tests for truthful analytics ingestion responses."""
from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient

from analytics_ingestion import main
from analytics_ingestion.youtube_analytics_client import VideoMetrics


class FailingWriter:
    def __init__(self) -> None:
        self.records = []

    async def write_metrics(self, metrics) -> None:
        self.records.append(metrics)

    async def flush(self) -> None:
        raise RuntimeError("warehouse unavailable")


class FakeYouTubeClient:
    async def fetch_video_metrics(self, video_ids, channel_id):
        return [
            VideoMetrics(
                video_id=video_ids[0],
                channel_id=channel_id,
                views=1,
                likes=0,
                comments=0,
                shares=0,
                watch_time_seconds=0,
                average_view_duration_seconds=0.0,
                ctr=0.0,
                retention_curve=[],
                subscriber_gain=0,
                measured_at=datetime(2024, 1, 1),
            )
        ]


def test_ingest_write_failure_does_not_report_success(monkeypatch) -> None:
    fake_writer = FailingWriter()
    monkeypatch.setattr(main, "writer", fake_writer)
    monkeypatch.setattr(main, "yt_client", FakeYouTubeClient())

    response = TestClient(main.app).post(
        "/api/v1/ingest/youtube",
        params={"channel_id": "channel-1"},
        json=["video-1"],
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "warehouse unavailable"
    assert len(fake_writer.records) == 1
