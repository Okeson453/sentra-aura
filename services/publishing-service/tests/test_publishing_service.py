"""Test suite for the Publishing Service.

Covers health checks, CRUD operations, and error handling.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from publishing_service.main import app, _store


client = TestClient(app)


class TestHealth:
    """Tests for health endpoints."""

    def test_health_check(self) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_ready_check(self) -> None:
        response = client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestAuth:
    """Tests for authentication."""

    def test_missing_auth(self) -> None:
        response = client.get("/platforms")
        assert response.status_code == 401

    def test_invalid_auth(self) -> None:
        response = client.get("/platforms", headers={"Authorization": "Invalid"})
        assert response.status_code == 401
