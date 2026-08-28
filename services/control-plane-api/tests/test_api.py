"""Tests for the Control Plane API."""
from __future__ import annotations

import pytest
pytest.importorskip("psycopg2")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from control_plane_api.main import create_app
from control_plane_api.models import Base
from control_plane_api.api.dependencies import get_db

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app = create_app()
app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_create_and_get_channel():
    resp = client.post("/api/v1/channels", json={"name": "Test Channel", "platform": "youtube", "tenant_id": "T1"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Test Channel"

    ch_id = data["id"]
    resp2 = client.get(f"/api/v1/channels/{ch_id}")
    assert resp2.status_code == 200
    assert resp2.json()["name"] == "Test Channel"


def test_list_channels():
    resp = client.get("/api/v1/channels")
    assert resp.status_code == 200
    assert "items" in resp.json()


def test_create_content_plan():
    resp = client.post("/api/v1/content/plans", json={"channel_id": "C1", "topic": "AI Trends"})
    assert resp.status_code == 200
    assert resp.json()["topic"] == "AI Trends"


def test_create_script():
    resp = client.post("/api/v1/content/scripts", json={"content_plan_id": "P1", "title": "Draft"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "Draft"


def test_create_video():
    resp = client.post("/api/v1/content/videos", json={"script_id": "S1", "channel_id": "C1"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "RENDERING"


def test_create_clip():
    resp = client.post("/api/v1/content/clips", json={"video_id": "V1", "channel_id": "C1"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "READY_TO_PUBLISH"


def test_create_publication():
    resp = client.post("/api/v1/publishing/publications", json={"channel_id": "C1", "platform": "youtube"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "SCHEDULED"


def test_create_experiment():
    resp = client.post("/api/v1/experiments", json={"channel_id": "C1", "name": "Test Exp", "hypothesis": "H1"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test Exp"


def test_create_policy():
    resp = client.post("/api/v1/policies", json={"channel_id": "C1", "policy_type": "autonomy", "autonomy_level": "L2"})
    assert resp.status_code == 200
    assert resp.json()["autonomy_level"] == "L2"


def test_create_decision():
    resp = client.post("/api/v1/decisions", json={"channel_id": "C1", "agent_type": "TestAgent", "decision": "approve"})
    assert resp.status_code == 200
    assert resp.json()["decision"] == "approve"
