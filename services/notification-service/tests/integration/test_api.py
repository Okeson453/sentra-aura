"""Integration tests for notification service API."""
from __future__ import annotations

from fastapi.testclient import TestClient

from notification_service.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_send_alert():
    payload = {
        "alert_id": "test-001",
        "severity": "error",
        "title": "Test Alert",
        "message": "This is a test alert",
        "source_service": "test-service",
    }
    response = client.post("/api/v1/alerts", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["alert_id"] == "test-001"
    assert data["routed"] is True


def test_acknowledge_alert():
    # First send an alert
    payload = {
        "alert_id": "test-002",
        "severity": "error",
        "title": "Ack Test",
        "message": "msg",
        "source_service": "test-svc",
    }
    client.post("/api/v1/alerts", json=payload)

    response = client.post("/api/v1/alerts/test-002/acknowledge")
    assert response.status_code == 200
    assert response.json()["acknowledged"] is True


def test_routing_table():
    response = client.get("/api/v1/routing")
    assert response.status_code == 200
    data = response.json()
    assert "critical" in data
    assert "error" in data
