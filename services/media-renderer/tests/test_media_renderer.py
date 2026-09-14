"""Test suite for the Media Renderer.

Covers health checks, CRUD operations, and error handling.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from media_renderer.main import app


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
    """Tests for authentication.

    These previously targeted ``/platforms`` - a route that exists nowhere in
    this service (the request 404'd, so the assertions proved nothing about
    authentication). They now exercise a real authenticated route, which is
    what makes the expected 401 meaningful.
    """

    AUTHENTICATED_ROUTE = "/render/jobs"

    def test_missing_auth(self) -> None:
        response = client.get(self.AUTHENTICATED_ROUTE)
        assert response.status_code == 401

    def test_invalid_auth(self) -> None:
        response = client.get(self.AUTHENTICATED_ROUTE, headers={"Authorization": "Invalid"})
        assert response.status_code == 401
