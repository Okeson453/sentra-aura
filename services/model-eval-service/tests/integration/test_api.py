"""Integration tests for model eval API."""
from __future__ import annotations

from fastapi.testclient import TestClient

from model_eval_service.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_drift_baseline():
    response = client.post(
        "/api/v1/drift/baseline",
        params={"agent_id": "test-agent", "version": "1.0.0"},
        json=[0.8, 0.85, 0.82],
    )
    assert response.status_code == 200
    assert response.json()["baseline_set"] is True


def test_drift_detect():
    client.post(
        "/api/v1/drift/baseline",
        params={"agent_id": "test-agent", "version": "1.0.0"},
        json=[0.8, 0.85, 0.82],
    )
    response = client.post(
        "/api/v1/drift/detect",
        params={"agent_id": "test-agent", "version": "1.0.0"},
        json=[0.8, 0.85, 0.82],
    )
    assert response.status_code == 200
    data = response.json()
    assert "drift_detected" in data
