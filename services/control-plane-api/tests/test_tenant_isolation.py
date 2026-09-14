"""Tenant-isolation regression tests for the Control Plane API.

These tests pin the behaviour of a previously exploitable defect: tenant
identity was taken from an unauthenticated ``X-Tenant-ID`` header / query
parameter / request body, and the channel repository applied no tenant filter
on get/update/delete.  Any authenticated principal could therefore read,
mutate and delete another tenant's channels.

Each test below fails against the pre-fix implementation.
"""
from __future__ import annotations

import pytest

pytest.importorskip("psycopg2")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from control_plane_api.main import create_app  # noqa: E402
from control_plane_api.models import Base  # noqa: E402
from control_plane_api.api.dependencies import get_db, get_db_session  # noqa: E402
from control_plane_api.config import get_settings  # noqa: E402
from sentinel_security import create_service_token  # noqa: E402

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def _override():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app = create_app()
app.dependency_overrides[get_db] = _override
app.dependency_overrides[get_db_session] = _override
client = TestClient(app)

_SECRET = get_settings().jwt_secret


def _headers(tenant: str | None) -> dict[str, str]:
    token = create_service_token(
        "iso-test",
        ["admin"],
        secret=_SECRET,
        ttl_seconds=3600,
        tenant_id=tenant,
    )
    return {"Authorization": f"Bearer {token}"}


A = _headers("tenant-a")
B = _headers("tenant-b")
NO_TENANT = _headers(None)


def _create(tenant_body: str, headers: dict[str, str], name: str = "chan"):
    return client.post(
        "/api/v1/channels",
        headers=headers,
        json={"name": name, "platform": "youtube", "tenant_id": tenant_body},
    )


@pytest.fixture(scope="module")
def channel_a() -> str:
    resp = _create("tenant-a", A, "A channel")
    assert resp.status_code == 201, resp.text
    # The row is owned by the authenticated tenant.
    assert resp.json()["tenant_id"] == "tenant-a"
    return resp.json()["id"]


def test_token_without_tenant_claim_is_rejected():
    """A credential that carries no tenant cannot scope a data access."""
    assert client.get("/api/v1/channels", headers=NO_TENANT).status_code == 401
    assert _create("tenant-a", NO_TENANT).status_code == 401


def test_body_cannot_impersonate_another_tenant():
    """Creating a row inside a tenant the caller does not own is refused."""
    resp = _create("tenant-b", A, "stolen")
    assert resp.status_code == 403, resp.text


def test_body_tenant_must_be_omitted_or_match_the_token():
    """The body may only restate the authenticated tenant.

    ``tenant_id`` is still a required field of the create schema, but it is an
    assertion to be checked, never the source of truth: omitting it is a
    validation error, naming the caller's own tenant is accepted, and naming
    anyone else's is rejected (see
    :func:`test_body_cannot_impersonate_another_tenant`).
    """
    omitted = client.post(
        "/api/v1/channels",
        headers=A,
        json={"name": "implicit", "platform": "youtube"},
    )
    assert omitted.status_code == 422, omitted.text

    matching = _create("tenant-a", A, "matching")
    assert matching.status_code == 201, matching.text
    assert matching.json()["tenant_id"] == "tenant-a"


def test_cross_tenant_read_is_denied(channel_a: str):
    """B must not be able to read A's channel (was 200 before the fix)."""
    assert client.get(f"/api/v1/channels/{channel_a}", headers=B).status_code == 404
    # ...while the owner still can.
    assert client.get(f"/api/v1/channels/{channel_a}", headers=A).status_code == 200


def test_cross_tenant_update_is_denied(channel_a: str):
    """B must not be able to mutate A's channel (was 200 before the fix)."""
    resp = client.patch(
        f"/api/v1/channels/{channel_a}", headers=B, json={"name": "hijacked"}
    )
    assert resp.status_code == 404, resp.text
    # The attempted write did not land.
    assert client.get(f"/api/v1/channels/{channel_a}", headers=A).json()["name"] == "A channel"


def test_cross_tenant_delete_is_denied(channel_a: str):
    """B must not be able to delete A's channel (was 204 before the fix)."""
    assert client.delete(f"/api/v1/channels/{channel_a}", headers=B).status_code == 404
    assert client.get(f"/api/v1/channels/{channel_a}", headers=A).status_code == 200


def test_listing_is_scoped_to_the_authenticated_tenant():
    """An unfiltered listing must never expose another tenant's rows."""
    assert _create("tenant-b", B, "B channel").status_code == 201

    seen_a = {c["tenant_id"] for c in client.get("/api/v1/channels", headers=A).json()["items"]}
    seen_b = {c["tenant_id"] for c in client.get("/api/v1/channels", headers=B).json()["items"]}

    assert seen_a == {"tenant-a"}, seen_a
    assert seen_b == {"tenant-b"}, seen_b


def test_tenant_header_cannot_widen_scope(channel_a: str):
    """The legacy X-Tenant-ID header must not influence the scope."""
    widened = dict(B)
    widened["X-Tenant-ID"] = "tenant-a"
    assert client.get(f"/api/v1/channels/{channel_a}", headers=widened).status_code == 404
    assert _create("tenant-a", widened, "via-header").status_code == 403
