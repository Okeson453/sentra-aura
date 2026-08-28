"""Integration tests for analytics ingestion API."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from analytics_ingestion.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_ready():
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_normalize_endpoint():
    payload = {
        "raw_metrics": {
            "video_id": "v1",
            "channel_id": "c1",
            "views": 5000,
            "ctr": 0.06,
            "average_view_duration_seconds": 200.0,
            "watch_time_seconds": 400000,
            "likes": 300,
            "comments": 50,
            "measured_at": "2024-01-15T12:00:00",
        },
        "channel_baseline": {"avg_ctr": 0.05, "avg_duration": 180.0, "avg_watch_time": 300000.0, "avg_engagement": 0.02},
    }
    response = client.post("/api/v1/normalize", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["video_id"] == "v1"
    assert "composite_score" in data
