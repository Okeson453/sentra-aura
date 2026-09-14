"""Unit tests for the tenant-isolation primitives.

These functions are the enforcement point for the platform-wide rule that
tenant identity comes from authenticated context, never from the request.
"""
from __future__ import annotations

import pytest

from sentinel_exceptions import AuthorizationError
from sentinel_security import (
    auth_error_to_http_status,
    resolve_tenant_id,
    validate_tenant_id,
)
from sentinel_security.auth import AuthContext


class _Ctx:
    """Minimal stand-in for a verified AuthContext."""

    def __init__(self, tenant_id: str | None, subject: str = "service:test") -> None:
        self.tenant_id = tenant_id
        self.subject = subject


# --- validate_tenant_id ----------------------------------------------------

@pytest.mark.parametrize("value", [None, "", "   "])
def test_validate_rejects_missing_tenant(value):
    with pytest.raises(AuthorizationError, match="could not be derived"):
        validate_tenant_id(value)


def test_validate_rejects_overlong_tenant():
    with pytest.raises(AuthorizationError, match="maximum length"):
        validate_tenant_id("t" * 33)


@pytest.mark.parametrize("value", ["bad tenant", "tenant/../etc", "<script>", "a" * 33])
def test_validate_rejects_malformed_tenant(value):
    with pytest.raises(AuthorizationError):
        validate_tenant_id(value)


@pytest.mark.parametrize("value", ["tenant-a", "t_1", "org.example", "ACME:prod"])
def test_validate_accepts_well_formed_tenant(value):
    assert validate_tenant_id(value) == value


# --- resolve_tenant_id -----------------------------------------------------

def test_missing_token_tenant_fails_closed():
    """A credential with no tenant claim cannot scope an access."""
    with pytest.raises(AuthorizationError):
        resolve_tenant_id(_Ctx(None), None, enforce_isolation=True)


def test_token_tenant_is_authoritative():
    assert resolve_tenant_id(_Ctx("tenant-a"), "tenant-a") == "tenant-a"


def test_mismatched_tenant_is_rejected():
    """The core exploit: naming another tenant must not be honoured."""
    with pytest.raises(AuthorizationError, match="Tenant mismatch"):
        resolve_tenant_id(_Ctx("tenant-a"), "tenant-b", enforce_isolation=True)


def test_transitional_mode_prefers_token_then_tolerates_request():
    """With isolation not yet enforced, the claim still wins."""
    assert resolve_tenant_id(_Ctx("tenant-a"), "tenant-b", enforce_isolation=False) == "tenant-a"
    assert resolve_tenant_id(_Ctx(None), "tenant-b", enforce_isolation=False) == "tenant-b"


def test_transitional_mode_still_fails_closed_without_either():
    with pytest.raises(AuthorizationError):
        resolve_tenant_id(_Ctx(None), None, enforce_isolation=False)


# --- AuthContext carries the verified claim -------------------------------

def test_auth_context_exposes_token_tenant_claim():
    ctx = AuthContext(
        subject="service:x",
        subject_type="service",
        roles=[],
        claims={"tenant_id": "from-claim"},
    )
    assert ctx.tenant_id == "from-claim"


def test_auth_context_supports_org_id_alias():
    ctx = AuthContext(
        subject="service:x", subject_type="service", roles=[], claims={"org_id": "org-9"}
    )
    assert ctx.tenant_id == "org-9"


def test_auth_context_has_no_tenant_when_unclaimed():
    ctx = AuthContext(subject="service:x", subject_type="service", roles=[], claims={})
    assert ctx.tenant_id is None


# --- status mapping -------------------------------------------------------

def test_missing_claim_maps_to_401_and_mismatch_to_403():
    assert auth_error_to_http_status(
        AuthorizationError("Tenant identity could not be derived from the authenticated token")
    ) == 401
    assert auth_error_to_http_status(
        AuthorizationError("Tenant mismatch: nope")
    ) == 403
