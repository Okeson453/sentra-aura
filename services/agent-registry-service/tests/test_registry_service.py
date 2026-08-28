"""Tests for the Agent Registry Service."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agent_registry_service.main import app, store
from agent_registry_service.models import (
    AgentRegistration,
    AgentStatus,
    EvaluationRecord,
    EvaluationStatus,
    HealthStatus,
)


@pytest.fixture(autouse=True)
def reset_store():
    """Reset store before each test."""
    store._agents.clear()
    store._health.clear()
    store._versions.clear()
    store._evaluations.clear()
    yield


@pytest.fixture
def client():
    return TestClient(app)


class TestHealth:
    def test_health_check(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_ready_check(self, client):
        resp = client.get("/ready")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ready"


class TestAgentRegistration:
    def test_register_and_get(self, client):
        payload = {
            "agent_id": "test_agent",
            "name": "Test Agent",
            "domain": "test",
            "version": "1.0.0",
            "capabilities": ["test"],
            "endpoint": "agents/test_agent",
        }
        resp = client.post("/api/v1/agents", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["agent_id"] == "test_agent"

        resp = client.get("/api/v1/agents/test_agent")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test Agent"

    def test_register_duplicate(self, client):
        payload = {
            "agent_id": "dup_agent",
            "name": "Dup",
            "domain": "test",
            "version": "1.0.0",
        }
        client.post("/api/v1/agents", json=payload)
        resp = client.post("/api/v1/agents", json=payload)
        assert resp.status_code == 409

    def test_list_agents(self, client):
        for i in range(3):
            client.post("/api/v1/agents", json={
                "agent_id": f"agent_{i}",
                "name": f"Agent {i}",
                "domain": "test" if i < 2 else "other",
                "version": "1.0.0",
            })
        resp = client.get("/api/v1/agents?domain=test")
        assert len(resp.json()) == 2

    def test_unregister(self, client):
        client.post("/api/v1/agents", json={
            "agent_id": "to_remove",
            "name": "Remove Me",
            "domain": "test",
            "version": "1.0.0",
        })
        resp = client.delete("/api/v1/agents/to_remove")
        assert resp.status_code == 204
        resp = client.get("/api/v1/agents/to_remove")
        assert resp.status_code == 404


class TestHealthEndpoints:
    def test_update_and_get_health(self, client):
        client.post("/api/v1/agents", json={
            "agent_id": "health_agent",
            "name": "Health Agent",
            "domain": "test",
            "version": "1.0.0",
        })
        resp = client.patch("/api/v1/agents/health_agent/health", json={"health": "degraded"})
        assert resp.status_code == 200
        assert resp.json()["health"] == "degraded"

        resp = client.get("/api/v1/agents/health_agent/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "degraded"


class TestEvaluations:
    def test_submit_and_get_canary(self, client):
        client.post("/api/v1/agents", json={
            "agent_id": "eval_agent",
            "name": "Eval Agent",
            "domain": "test",
            "version": "1.0.0",
        })
        resp = client.post("/api/v1/agents/eval_agent/evaluations", json={
            "agent_id": "eval_agent",
            "status": "canary",
            "score": 0.92,
            "evaluator": "test_suite",
            "notes": "Test CANARY record",
        })
        assert resp.status_code == 200
        assert resp.json()["score"] == 0.92

        resp = client.get("/api/v1/agents/eval_agent/evaluations/canary")
        assert resp.status_code == 200
        assert resp.json()["canary"]["score"] == 0.92

    def test_get_all_evaluations(self, client):
        client.post("/api/v1/agents", json={
            "agent_id": "multi_eval",
            "name": "Multi Eval",
            "domain": "test",
            "version": "1.0.0",
        })
        for status in ["canary", "staging", "production"]:
            client.post("/api/v1/agents/multi_eval/evaluations", json={
                "agent_id": "multi_eval",
                "status": status,
                "score": 0.8,
                "evaluator": "test",
            })
        resp = client.get("/api/v1/agents/multi_eval/evaluations")
        assert len(resp.json()) == 3
