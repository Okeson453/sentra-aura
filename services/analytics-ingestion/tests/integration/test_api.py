"""Integration tests for analytics ingestion API."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sentinel_security import create_service_token

from analytics_ingestion.config import config as analytics_config
from analytics_ingestion.main import app

client = TestClient(app)


def _headers(tenant_id: str = "tenant-aaa") -> dict[str, str]:
    """A valid service token.

    ``/api/v1/normalize`` is now authenticated at the application boundary: it
    handles tenant-sensitive performance data, so an unauthenticated caller is
    rejected with 401 rather than served.
    """
    token = create_service_token(
        "analytics-ingestion",
        ["service"],
        secret=analytics_config.jwt_secret,
        tenant_id=tenant_id,
    )
    return {"Authorization": f"Bearer {token}"}


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
    response = client.post("/api/v1/normalize", json=payload, headers=_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["video_id"] == "v1"
    assert "composite_score" in data


def test_normalize_rejects_anonymous_callers():
    """Tenant-sensitive analytics input must not be served without a credential."""
    payload = {
        "raw_metrics": {"video_id": "v1", "channel_id": "c1", "views": 1, "measured_at": "2024-01-15T12:00:00"},
        "channel_baseline": {"avg_ctr": 0.05, "avg_duration": 180.0, "avg_watch_time": 300000.0, "avg_engagement": 0.02},
    }
    assert client.post("/api/v1/normalize", json=payload).status_code == 401


def test_normalize_rejects_a_cross_tenant_assertion():
    """A caller may not act for a tenant it was not authenticated as."""
    payload = {
        "raw_metrics": {
            "video_id": "v1",
            "channel_id": "c1",
            "tenant_id": "tenant-bbb",
            "views": 1,
            "measured_at": "2024-01-15T12:00:00",
        },
        "channel_baseline": {"avg_ctr": 0.05, "avg_duration": 180.0, "avg_watch_time": 300000.0, "avg_engagement": 0.02},
    }
    response = client.post("/api/v1/normalize", json=payload, headers=_headers("tenant-aaa"))
    assert response.status_code == 403
