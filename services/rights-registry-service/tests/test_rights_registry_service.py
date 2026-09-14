"""Test suite for the Rights Registry Service.

Covers health checks, CRUD operations, authentication enforcement, and
rights/permission enforcement.
"""
from __future__ import annotations

import time

import jwt
import pytest
from fastapi.testclient import TestClient

from rights_registry_service.config import ServiceConfig
from rights_registry_service.main import _store, app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_store():
    """Isolate tests: the service keeps its records in a module-level store."""
    _store.clear()
    yield
    _store.clear()


def _token(**overrides: object) -> str:
    payload: dict[str, object] = {
        "sub": "svc-test",
        "subject_type": "service",
        "roles": ["admin"],
        "exp": int(time.time()) + 600,
    }
    payload.update(overrides)
    return jwt.encode(payload, ServiceConfig().jwt_secret, algorithm="HS256")


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {_token()}"}


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
        # /ready used to return a hard-coded empty checks map, which made the
        # readiness probe unconditionally report healthy.
        assert data["checks"]
        assert all(c["status"] == "pass" for c in data["checks"].values())


class TestAuth:
    """Tests for authentication."""

    def test_missing_auth(self) -> None:
        response = client.get("/rights")
        assert response.status_code == 401

    def test_invalid_auth(self) -> None:
        response = client.get("/rights", headers={"Authorization": "Invalid"})
        assert response.status_code == 401


class TestAuthEnforcement:
    """Regression guard for a complete authentication bypass.

    Every business route declared ``authorization: str = _require_bearer`` as a
    bare default. FastAPI does not execute a plain default value, so the
    ``_require_bearer`` function was never called: it was exposed as an optional
    *query parameter* instead, and the routes were fully unauthenticated. Both
    the resulting empty ``dependant.dependencies`` and the absence of the bare
    default are asserted here so the pattern cannot silently return.
    """

    def test_routes_declare_a_real_auth_dependency(self) -> None:
        from fastapi.routing import APIRoute

        checked = 0
        for route in app.routes:
            if not isinstance(route, APIRoute):
                continue
            if route.path in ("/health", "/ready", "/metrics"):
                continue
            assert route.dependant.dependencies, f"{route.path} has no auth dependency"
            names = [p.name for p in route.dependant.query_params]
            assert "authorization" not in names, f"{route.path} leaked auth as a query parameter"
            checked += 1
        assert checked >= 7

    def test_no_bare_helper_default_remains(self) -> None:
        import inspect

        import rights_registry_service.main as main_module

        source = inspect.getsource(main_module)
        assert "= _require_bearer)" not in source, "auth helper used as a bare default again"
        assert "Depends(_require_bearer)" in source

    def test_missing_token_is_rejected(self) -> None:
        assert client.post("/rights", json={"asset_id": "a", "owner": "o"}).status_code == 401

    def test_garbage_token_is_rejected(self) -> None:
        response = client.post(
            "/rights",
            headers={"Authorization": "Bearer not-a-jwt"},
            json={"asset_id": "a", "owner": "o"},
        )
        assert response.status_code == 401

    def test_valid_token_is_accepted(self) -> None:
        response = client.post("/rights", headers=_auth(), json={"asset_id": "a", "owner": "o"})
        assert response.status_code == 200


class TestRightsEnforcement:
    """Regression guard: /rights/{id}/check returned a hard-coded ``permitted: True``."""

    def _register(self) -> str:
        body = {
            "asset_id": "asset-1",
            "owner": "owner-1",
            "permitted_usage": ["clipping"],
            "restricted_usage": ["monetization"],
            "attribution_required": True,
            "attribution_text": "Courtesy of SentraAura",
        }
        response = client.post("/rights", headers=_auth(), json=body)
        assert response.status_code == 200
        return str(response.json()["rights_id"])

    def test_permitted_usage_is_approved(self) -> None:
        rights_id = self._register()
        response = client.post(f"/rights/{rights_id}/check", headers=_auth(), json={"usage_type": "clipping"})
        assert response.json()["permitted"] is True
        assert response.json()["attribution_required"] is True

    def test_explicitly_restricted_usage_is_denied(self) -> None:
        rights_id = self._register()
        response = client.post(f"/rights/{rights_id}/check", headers=_auth(), json={"usage_type": "monetization"})
        assert response.json()["permitted"] is False

    def test_usage_outside_allow_list_is_denied(self) -> None:
        rights_id = self._register()
        response = client.post(f"/rights/{rights_id}/check", headers=_auth(), json={"usage_type": "rebroadcast"})
        assert response.json()["permitted"] is False

    def test_unknown_rights_record_is_a_404(self) -> None:
        response = client.post("/rights/does-not-exist/check", headers=_auth(), json={"usage_type": "clipping"})
        assert response.status_code == 404

    def test_get_rights_round_trips(self) -> None:
        rights_id = self._register()
        response = client.get(f"/rights/{rights_id}", headers=_auth())
        assert response.status_code == 200
        assert response.json()["rights_id"] == rights_id
