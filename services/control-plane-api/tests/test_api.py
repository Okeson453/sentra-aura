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
from control_plane_api.api.dependencies import get_db, get_db_session
from control_plane_api.config import get_settings
from sentinel_security import create_service_token

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
# The route handlers depend on ``get_db_session`` (a distinct dependency from
# ``get_db``), so it must be overridden as well for requests to be served from
# the in-memory test database instead of the configured Postgres URL.
app.dependency_overrides[get_db_session] = override_get_db
client = TestClient(app)


@pytest.fixture(scope="module")
def auth_header() -> dict[str, str]:
    """Mint a valid service JWT for the app's configured signing secret.

    ``create_app()`` enables ``AuthenticationMiddleware(require_auth=True)`` so
    every non-exempt request must carry a valid ``Authorization: Bearer`` token.
    """
    settings = get_settings()
    token = create_service_token(
        "control-plane-api-tests",
        ["admin"],
        secret=settings.jwt_secret,
        ttl_seconds=3600,
        # Tenant identity must be bound into the verified token; the API now
        # derives the tenant scope from this claim rather than from a
        # client-supplied header/body.
        tenant_id="T1",
    )
    return {"Authorization": f"Bearer {token}"}


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_unauthenticated_requests_are_rejected():
    """Fail-closed guard: missing or invalid credentials must never reach a route."""
    assert client.get("/api/v1/channels").status_code == 401
    assert (
        client.post(
            "/api/v1/channels",
            json={"name": "x", "platform": "youtube", "tenant_id": "T1"},
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/api/v1/channels",
            headers={"Authorization": "Bearer not-a-jwt"},
        ).status_code
        == 401
    )


def test_create_and_get_channel(auth_header):
    resp = client.post(
        "/api/v1/channels",
        headers=auth_header,
        json={"name": "Test Channel", "platform": "youtube", "tenant_id": "T1"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Channel"

    ch_id = data["id"]
    resp2 = client.get(f"/api/v1/channels/{ch_id}", headers=auth_header)
    assert resp2.status_code == 200
    assert resp2.json()["name"] == "Test Channel"


def test_list_channels(auth_header):
    resp = client.get("/api/v1/channels", headers=auth_header)
    assert resp.status_code == 200
    assert "items" in resp.json()


def test_create_content_plan(auth_header):
    resp = client.post(
        "/api/v1/content/plans",
        headers=auth_header,
        json={"channel_id": "C1", "topic": "AI Trends"},
    )
    assert resp.status_code == 201
    assert resp.json()["topic"] == "AI Trends"


def test_create_script(auth_header):
    resp = client.post(
        "/api/v1/content/scripts",
        headers=auth_header,
        json={"content_plan_id": "P1", "title": "Draft"},
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "Draft"


def test_create_video(auth_header):
    resp = client.post(
        "/api/v1/content/videos",
        headers=auth_header,
        json={"script_id": "S1", "channel_id": "C1"},
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "RENDERING"


def test_create_clip(auth_header):
    resp = client.post(
        "/api/v1/content/clips",
        headers=auth_header,
        json={"video_id": "V1", "channel_id": "C1"},
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "READY_TO_PUBLISH"


def test_create_publication(auth_header):
    resp = client.post(
        "/api/v1/publishing/publications",
        headers=auth_header,
        json={"channel_id": "C1", "platform": "youtube"},
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "SCHEDULED"


def test_create_experiment(auth_header):
    resp = client.post(
        "/api/v1/experiments",
        headers=auth_header,
        json={"channel_id": "C1", "name": "Test Exp", "hypothesis": "H1"},
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Test Exp"


def test_create_policy(auth_header):
    resp = client.post(
        "/api/v1/policies",
        headers=auth_header,
        json={"channel_id": "C1", "policy_type": "autonomy", "autonomy_level": "L2"},
    )
    assert resp.status_code == 201
    assert resp.json()["autonomy_level"] == "L2"


def test_create_decision(auth_header):
    resp = client.post(
        "/api/v1/decisions",
        headers=auth_header,
        json={"channel_id": "C1", "agent_type": "TestAgent", "decision": "approve"},
    )
    assert resp.status_code == 201
    assert resp.json()["decision"] == "approve"
