"""Tenant-context middleware contracts.

Every test here fails against the pre-fix middleware, which read the acting
tenant from the unauthenticated ``X-Tenant-ID`` header (with a
``/tenants/<id>`` path fallback) and never armed the ORM row-level-security
hook.  Together those two defects let a caller holding a token for one tenant
read and mutate another tenant's data.
"""
from __future__ import annotations

import sys
import types
from contextvars import ContextVar

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from service_kit import middleware as mw
from sentinel_security.auth import create_service_token

SECRET = "test-secret-value-that-is-long-enough-for-hs256"

TENANT_A = "tenant-aaa"
TENANT_B = "tenant-bbb"


def _token(tenant_id: str | None, roles: list[str] | None = None) -> str:
    return create_service_token(
        "svc", roles or ["reader"], secret=SECRET, tenant_id=tenant_id
    )


AUTH_A = {"Authorization": f"Bearer {_token(TENANT_A)}"}


@pytest.fixture
def rls_module(monkeypatch):
    """Install a synthetic RLS primitive module.

    Tests the *wiring* -- that the middleware arms and resets the tenant
    context per request -- without depending on any particular service's
    ``db.base``.  The real hook is covered by
    ``services/control-plane-api/tests/test_rls_isolation.py``.
    """
    module = types.ModuleType("poc_rls_db_base")
    current: ContextVar[str | None] = ContextVar("poc_tenant", default=None)
    module.set_tenant_context = current.set
    module.get_tenant_context = current.get
    module.reset_tenant_context = current.reset
    sys.modules["poc_rls_db_base"] = module
    monkeypatch.setattr(mw, "RLS_DB_BASE_MODULES", ("poc_rls_db_base",))
    yield module
    # Nothing leaked out of the request.
    assert current.get() is None, "tenant context leaked past the request"
    sys.modules.pop("poc_rls_db_base", None)


def _app(*, require_auth: bool = True, isolation: bool = True) -> FastAPI:
    app = FastAPI()

    @app.get("/probe")
    async def probe(request: Request):
        auth = getattr(request.state, "auth_context", None)
        return {
            "state_tenant": getattr(request.state, "tenant_id", None),
            "auth_tenant": getattr(auth, "tenant_id", None) if auth else None,
            "rls_tenant": (
                sys.modules["poc_rls_db_base"].get_tenant_context()
                if "poc_rls_db_base" in sys.modules
                else None
            ),
        }

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    mw.setup_middleware(
        app,
        jwt_secret=SECRET,
        jwt_algorithm="HS256",
        require_auth=require_auth,
        enforce_tenant_isolation=isolation,
    )
    return app


class TestTenantComesFromTheToken:
    def test_header_cannot_override_the_authenticated_tenant(self, rls_module):
        """A caller asserting another tenant must not widen its own scope."""
        client = TestClient(_app())
        r = client.get("/probe", headers={**AUTH_A, "X-Tenant-ID": TENANT_B})
        assert r.status_code == 200
        assert r.json()["state_tenant"] == TENANT_A
        assert r.json()["auth_tenant"] == TENANT_A

    def test_query_parameter_cannot_override_the_authenticated_tenant(self, rls_module):
        client = TestClient(_app())
        r = client.get(f"/probe?tenant_id={TENANT_B}", headers=AUTH_A)
        assert r.status_code == 200
        assert r.json()["state_tenant"] == TENANT_A

    def test_authenticated_tenant_is_used_when_nothing_is_asserted(self, rls_module):
        client = TestClient(_app())
        r = client.get("/probe", headers=AUTH_A)
        assert r.status_code == 200
        assert r.json()["state_tenant"] == TENANT_A

    def test_tenant_less_token_yields_no_tenant_context(self, rls_module):
        """No authenticated tenant: withhold the context, never invent one."""
        client = TestClient(_app())
        token = _token(None)
        r = client.get(
            "/probe",
            headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": TENANT_B},
        )
        assert r.status_code == 200
        assert r.json()["state_tenant"] is None, (
            "a header supplied tenant was accepted without an authenticated claim"
        )


class TestRlsIsArmed:
    def test_tenant_context_is_armed_for_the_request(self, rls_module):
        """The ORM RLS context must be set from the verified claim."""
        client = TestClient(_app())
        r = client.get("/probe", headers=AUTH_A)
        assert r.status_code == 200
        assert r.json()["rls_tenant"] == TENANT_A, (
            "the row-level-security context was not armed from the token"
        )

    def test_isolation_can_be_disabled_explicitly(self, rls_module):
        client = TestClient(_app(isolation=False))
        r = client.get("/probe", headers=AUTH_A)
        assert r.status_code == 200
        assert r.json()["rls_tenant"] is None


class TestAuthenticationPosture:
    def test_default_is_to_require_authentication(self):
        """A service must not become fail-open by omitting the argument."""
        from service_kit.config import ServiceConfig

        assert ServiceConfig().require_auth is True

    def test_unauthenticated_request_is_rejected(self, rls_module):
        client = TestClient(_app())
        assert client.get("/probe").status_code == 401

    def test_garbage_token_is_rejected(self, rls_module):
        client = TestClient(_app())
        r = client.get("/probe", headers={"Authorization": "Bearer not-a-jwt"})
        assert r.status_code == 401

    def test_explicit_opt_out_is_still_honoured(self, rls_module):
        """An intentionally open deployment opts out visibly."""
        client = TestClient(_app(require_auth=False))
        assert client.get("/probe").status_code == 200

    def test_health_is_exempt_from_authentication(self, rls_module):
        client = TestClient(_app())
        assert client.get("/health").status_code == 200
