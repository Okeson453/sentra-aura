#!/usr/bin/env python3
"""Negative regression suite: policy-engine must not serve unauthenticated or
cross-tenant callers.

Every test here corresponds to a violation reproduced against the pre-fix
service (``setup_middleware(app)`` with ``require_auth=False`` plus a
channel-keyed store), where ``GET /api/v1/policies/{channel_id}`` returned
HTTP 200 with another tenant's policies to a caller that sent no credential.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
for rel in (
    "services/policy-engine/src",
    "packages/sentinel-security/src",
    "packages/sentinel-exceptions/src",
    "packages/service-kit/src",
    "packages/observability/src",
):
    p = str(ROOT / rel)
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi.testclient import TestClient  # noqa: E402

from sentinel_security import create_service_token  # noqa: E402

SERVICE_SECRET = "unit-test-signing-secret-for-policy-engine-0001"
TENANT_A = "tenant-aaa"
TENANT_B = "tenant-bbb"


def _app(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SERVICE_SECRET)
    monkeypatch.setenv("ENVIRONMENT", "development")
    for mod in [m for m in list(sys.modules) if m.startswith("policy_engine")]:
        del sys.modules[mod]
    from policy_engine.main import app

    return app


def _token(tenant_id: str | None = TENANT_A) -> str:
    return create_service_token(
        "orchestrator",
        roles=["service"],
        secret=SERVICE_SECRET,
        tenant_id=tenant_id,
    )


def _auth(tenant_id: str | None = TENANT_A) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(tenant_id)}"}


@pytest.fixture()
def client(monkeypatch):
    with TestClient(_app(monkeypatch)) as c:
        yield c


class TestUnauthenticatedRequestsAreRejected:
    """No credential must never yield policy data."""

    def test_list_policies_without_credential_is_401(self, client):
        r = client.get(f"/api/v1/policies/{TENANT_B}-channel")
        assert r.status_code == 401, f"unauthenticated policy read returned {r.status_code}"

    def test_create_policy_without_credential_is_401(self, client):
        r = client.post(
            "/api/v1/policies",
            json={"rule_id": "r1", "channel_id": "chan-x", "action": "ALLOW"},
        )
        assert r.status_code == 401

    def test_evaluate_without_credential_is_401(self, client):
        r = client.post(
            "/api/v1/evaluate",
            json={"decision_id": "d1", "channel_id": "chan-x"},
        )
        assert r.status_code == 401

    def test_garbage_token_is_401(self, client):
        r = client.get(
            "/api/v1/policies/chan-x",
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert r.status_code == 401


class TestCrossTenantAccessIsDenied:
    """A credential may only act on its own tenant's policies."""

    def test_cross_tenant_channel_is_403(self, client):
        r = client.get(
            f"/api/v1/policies/{TENANT_B}::chan-1",
            headers=_auth(TENANT_A),
        )
        assert r.status_code == 403, "a channel naming another tenant was served"

    def test_body_tenant_assertion_is_rejected(self, client):
        r = client.post(
            "/api/v1/policies",
            json={
                "rule_id": "r-hopping",
                "channel_id": "chan-1",
                "tenant_id": TENANT_B,
                "action": "ALLOW",
            },
            headers=_auth(TENANT_A),
        )
        assert r.status_code == 403, "a body-supplied tenant widened the caller's scope"

    def test_token_without_tenant_is_rejected(self, client):
        r = client.get("/api/v1/policies/chan-1", headers=_auth(None))
        assert r.status_code in (401, 403), "a tenant-less token was served policy data"


class TestTenantScopedReads:
    def test_own_policy_is_visible_and_other_tenant_is_not(self, client):
        created = client.post(
            "/api/v1/policies",
            json={
                "rule_id": "r-a",
                "channel_id": "chan-1",
                "action": "BLOCK",
                "autonomy_level": "L2",
            },
            headers=_auth(TENANT_A),
        )
        assert created.status_code == 200, created.text

        own = client.get("/api/v1/policies/chan-1", headers=_auth(TENANT_A))
        assert own.status_code == 200
        assert [r["rule_id"] for r in own.json()] == ["r-a"]

        # Same channel id, different tenant: must not see tenant-a's rule.
        other = client.get("/api/v1/policies/chan-1", headers=_auth(TENANT_B))
        assert other.status_code == 200
        assert other.json() == [], "channel id leaked another tenant's policies"

    def test_evaluate_reports_threshold_not_missing_attribute(self, client):
        """The evaluation response must be serialisable and complete."""
        r = client.post(
            "/api/v1/evaluate",
            json={
                "decision_id": "d-1",
                "channel_id": "chan-1",
                "autonomy_level": "L1",
                "context": {"risk": {"content": 0.1}},
            },
            headers=_auth(TENANT_A),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["approved"] is True
        assert all("threshold" in rs for rs in body["risk_scores"])
