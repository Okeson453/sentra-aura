"""Integration tests for agent registry API."""
from __future__ import annotations

from fastapi.testclient import TestClient

from agent_registry_service.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_register_and_get():
    payload = {
        "agent_id": "int-test-agent",
        "name": "Integration Test Agent",
        "agent_type": "script_writer",
        "version": "1.0.0",
        "description": "Integration test",
        "capabilities": ["writing"],
        "config": {},
        "endpoints": [],
    }
    response = client.post("/api/v1/agents", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["agent_id"] == "int-test-agent"

    response = client.get("/api/v1/agents/int-test-agent")
    assert response.status_code == 200
    assert response.json()["agent_id"] == "int-test-agent"
