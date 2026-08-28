"""Test suite for the Clipping Engine.

Covers health checks, auth, and detect/score path.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from clipping_engine.main import app


client = TestClient(app)


class TestHealth:
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
    def test_missing_auth(self) -> None:
        response = client.post("/clips/detect", json={"video_id": "v1", "segments": []})
        assert response.status_code == 401

    def test_invalid_auth(self) -> None:
        response = client.post(
            "/clips/detect",
            headers={"Authorization": "Invalid"},
            json={"video_id": "v1", "segments": []},
        )
        assert response.status_code == 401


class TestDetectAndScore:
    def test_detect_returns_scored_candidates(self) -> None:
        response = client.post(
            "/clips/detect",
            headers={"Authorization": "Bearer dev-token"},
            json={
                "video_id": "v1",
                "segments": [
                    {
                        "segment_id": "s0",
                        "start_seconds": 0,
                        "end_seconds": 20,
                        "text": "Why does marine snow never settle?",
                        "visual_change": 0.9,
                    }
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["candidates"]
        assert "scores" in data["candidates"][0]
        assert "composite" in data["candidates"][0]["scores"]
