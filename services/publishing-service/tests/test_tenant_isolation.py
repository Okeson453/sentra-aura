"""Negative regression tests for tenant isolation on the publications API.

These tests exist because the publications API was previously filtered by
``publication_id`` alone: any authenticated principal could read, rename,
archive and *publish* another tenant's publications (broken object-level
authorization). Tenant identity now comes from the verified JWT claim and never
from the request; these tests fail against the pre-fix code on every path that
was exploitable.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sentinel_security.auth import create_service_token

from publishing_service import main as pubmain
from publishing_service.main import app

client = TestClient(app)

TENANT_A = "tenant-aaa"
TENANT_B = "tenant-bbb"


def _headers(tenant: str) -> dict[str, str]:
    token = create_service_token(
        "publishing-test", ["service"], secret=pubmain.config.jwt_secret,
        tenant_id=tenant,
    )
    return {"Authorization": f"Bearer {token}"}


def _headers_without_tenant() -> dict[str, str]:
    token = create_service_token(
        "publishing-test", ["service"], secret=pubmain.config.jwt_secret
    )
    return {"Authorization": f"Bearer {token}"}


def _seed(tenant: str) -> str:
    """Insert a publication owned by ``tenant``, bypassing the API."""
    publication_id = f"pub-{uuid.uuid4().hex[:12]}"
    session = pubmain.SessionLocal()
    try:
        session.add(
            pubmain.Publication(
                publication_id=publication_id,
                tenant_id=tenant,
                channel_id="seed-channel",
                title="seed-title",
                description="d",
                status="draft",
                asset_id="video.mp4",
                platforms=["youtube"],
                tags=[],
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
        session.commit()
    finally:
        session.close()
    return publication_id


def _load(publication_id: str) -> pubmain.Publication | None:
    session = pubmain.SessionLocal()
    try:
        return session.get(pubmain.Publication, publication_id)
    finally:
        session.close()


class TestCrossTenantReads:
    def test_get_other_tenants_publication_is_not_found(self) -> None:
        pid_a = _seed(TENANT_A)
        response = client.get(f"/publications/{pid_a}", headers=_headers(TENANT_B))
        assert response.status_code == 404

    def test_own_publication_is_readable(self) -> None:
        pid_a = _seed(TENANT_A)
        response = client.get(f"/publications/{pid_a}", headers=_headers(TENANT_A))
        assert response.status_code == 200
        assert response.json()["publication_id"] == pid_a

    def test_list_only_returns_own_publications(self) -> None:
        pid_a = _seed(TENANT_A)
        pid_b = _seed(TENANT_B)
        response = client.get("/publications", headers=_headers(TENANT_B))
        assert response.status_code == 200
        returned = {p["publication_id"] for p in response.json()["publications"]}
        assert pid_a not in returned, "another tenant's publication leaked into the list"
        assert pid_b in returned


class TestCrossTenantWrites:
    def test_update_other_tenants_publication_is_not_found_and_does_not_land(self) -> None:
        pid_a = _seed(TENANT_A)
        response = client.put(
            f"/publications/{pid_a}", headers=_headers(TENANT_B), json={"title": "HIJACKED"}
        )
        assert response.status_code == 404
        row = _load(pid_a)
        assert row is not None and row.title == "seed-title", "cross-tenant rename landed"

    def test_archive_other_tenants_publication_is_not_found_and_does_not_land(self) -> None:
        pid_b = _seed(TENANT_B)
        response = client.delete(f"/publications/{pid_b}", headers=_headers(TENANT_A))
        assert response.status_code == 404
        row = _load(pid_b)
        assert row is not None and row.status == "draft", "cross-tenant archive landed"

    def test_schedule_other_tenants_publication_is_not_found(self) -> None:
        pid_a = _seed(TENANT_A)
        response = client.post(
            f"/publications/{pid_a}/schedule",
            headers=_headers(TENANT_B),
            json={"scheduled_at": "2030-01-01T00:00:00Z"},
        )
        assert response.status_code == 404
        row = _load(pid_a)
        assert row is not None and row.status == "draft"

    def test_publish_other_tenants_publication_is_not_found(self) -> None:
        pid_b = _seed(TENANT_B)
        response = client.post(
            f"/publications/{pid_b}/publish", headers=_headers(TENANT_A), json={}
        )
        assert response.status_code == 404

    def test_unpublish_other_tenants_publication_is_not_found(self) -> None:
        pid_b = _seed(TENANT_B)
        response = client.post(
            f"/publications/{pid_b}/unpublish", headers=_headers(TENANT_A)
        )
        assert response.status_code == 404


class TestOwnershipIsAuthenticationDerived:
    def test_create_binds_ownership_to_the_token_tenant(self) -> None:
        response = client.post(
            "/publications",
            headers=_headers(TENANT_A),
            json={"channel_id": "c", "title": "t", "asset_id": "v.mp4"},
        )
        assert response.status_code == 200
        row = _load(response.json()["publication_id"])
        assert row is not None and row.tenant_id == TENANT_A

    def test_body_tenant_impersonation_is_rejected(self) -> None:
        response = client.post(
            "/publications",
            headers=_headers(TENANT_B),
            json={
                "channel_id": "c",
                "title": "t",
                "asset_id": "v.mp4",
                "tenant_id": TENANT_A,
            },
        )
        assert response.status_code == 403

    def test_update_body_tenant_impersonation_is_rejected(self) -> None:
        pid_b = _seed(TENANT_B)
        response = client.put(
            f"/publications/{pid_b}",
            headers=_headers(TENANT_B),
            json={"title": "t", "tenant_id": TENANT_A},
        )
        assert response.status_code == 403

    def test_missing_tenant_claim_fails_closed(self) -> None:
        _seed(TENANT_A)
        for method, url in (
            ("get", "/publications"),
            ("get", f"/publications/{_seed(TENANT_A)}"),
        ):
            response = getattr(client, method)(url, headers=_headers_without_tenant())
            assert response.status_code == 401, f"{method.upper()} {url} did not fail closed"

    def test_create_without_tenant_claim_fails_closed(self) -> None:
        response = client.post(
            "/publications",
            headers=_headers_without_tenant(),
            json={"channel_id": "c", "title": "t", "asset_id": "v.mp4"},
        )
        assert response.status_code == 401

    def test_legacy_header_cannot_widen_scope(self) -> None:
        """A client-supplied tenant header must never be consulted."""
        pid_a = _seed(TENANT_A)
        headers = dict(_headers(TENANT_B))
        headers["X-Tenant-ID"] = TENANT_A
        response = client.get(f"/publications/{pid_a}", headers=headers)
        assert response.status_code == 404, "X-Tenant-ID widened the caller's scope"
        response = client.get("/publications", headers=headers)
        assert response.status_code == 200
        returned = {p["publication_id"] for p in response.json()["publications"]}
        assert pid_a not in returned, "X-Tenant-ID widened the list scope"


def test_tenant_isolation_is_enforced_by_default() -> None:
    assert pubmain.config.enforce_tenant_isolation is True
