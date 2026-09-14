"""Tenant isolation primitives for SentraAura services.

Tenant identity is a security boundary.  It **must** originate from
authenticated context -- a verified JWT claim -- and must never be trusted
from a client-supplied header, query parameter or request body.  Accepting a
caller-supplied tenant identifier lets any authenticated principal read,
mutate and delete another tenant's data (a broken-object-level-authorization
defect).

This module provides the enforcement points:

* :func:`validate_tenant_id` -- shape/length validation, fails closed.
* :func:`resolve_tenant_id` -- derives the tenant a request is allowed to act
  on, and (when isolation is enforced) rejects any request whose requested
  tenant does not match the authenticated one.
* :func:`auth_error_to_http_status` -- maps an authorization failure onto the
  correct HTTP status without leaking a distinguishable oracle.

Behaviour is a pure function of its arguments so it can be unit-tested and
reused by every service.
"""
from __future__ import annotations

import hmac
import logging
import re
from typing import Any

from sentinel_exceptions import AuthorizationError

logger = logging.getLogger(__name__)

#: Longest tenant identifier the platform recognises (matches the
#: ``tenant_id`` column width used by the control plane schemas).
TENANT_ID_MAX_LENGTH = 32

#: A tenant id is an opaque, URL-safe token.  Rejecting anything else keeps
#: malformed input out of filter clauses and audit records.
_TENANT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,31}$")


def validate_tenant_id(tenant_id: str | None) -> str:
    """Return a normalised tenant id or raise :class:`AuthorizationError`.

    Raises rather than returning a sentinel so a missing/malformed tenant can
    never silently degrade into "no filter applied".
    """
    if tenant_id is None:
        raise AuthorizationError(
            "Tenant identity could not be derived from the authenticated token"
        )
    normalised = tenant_id.strip()
    if not normalised:
        raise AuthorizationError(
            "Tenant identity could not be derived from the authenticated token"
        )
    if len(normalised) > TENANT_ID_MAX_LENGTH:
        raise AuthorizationError("Tenant identifier exceeds the maximum length")
    if not _TENANT_ID_RE.match(normalised):
        raise AuthorizationError("Tenant identifier is malformed")
    return normalised


def resolve_tenant_id(
    auth_context: Any,
    requested_tenant_id: str | None = None,
    *,
    enforce_isolation: bool = True,
) -> str:
    """Resolve the tenant this request is authorised to act on.

    Parameters
    ----------
    auth_context:
        The :class:`~sentinel_security.auth.AuthContext` placed on
        ``request.state`` by the authentication middleware.
    requested_tenant_id:
        A tenant the caller *asked* to act on (body/query/path).  It is
        treated as an assertion to be verified, never as the source of truth.
    enforce_isolation:
        When True (production posture) the token claim is authoritative and a
        mismatch is rejected with ``403``.  When False the function still
        prefers the token claim but tolerates a caller-supplied value, which
        lets a deployment migrate callers before flipping the switch.

    Returns
    -------
    str
        The validated tenant identifier.

    Raises
    ------
    AuthorizationError
        If the token carries no tenant, or the requested tenant contradicts
        the authenticated one.
    """
    token_tenant = getattr(auth_context, "tenant_id", None) if auth_context else None
    requested = (requested_tenant_id or "").strip() or None

    if enforce_isolation:
        # The token is the single source of truth.
        tenant = validate_tenant_id(token_tenant)
        if requested is not None and not hmac.compare_digest(requested, tenant):
            logger.warning(
                "tenant_isolation_violation",
                extra={
                    "subject": getattr(auth_context, "subject", ""),
                    "token_tenant": tenant,
                    "requested_tenant": requested,
                },
            )
            raise AuthorizationError(
                "Tenant mismatch: the request targets a tenant the caller is not "
                "authorised to act on"
            )
        return tenant

    # Transitional mode: prefer the authenticated claim, tolerate an explicit
    # caller-supplied tenant, and fail closed when neither is present.
    if token_tenant:
        return validate_tenant_id(token_tenant)
    if requested:
        logger.info(
            "tenant_resolved_from_request",
            extra={"subject": getattr(auth_context, "subject", "")},
        )
        return validate_tenant_id(requested)
    raise AuthorizationError(
        "Tenant identity could not be derived from the authenticated token"
    )


def auth_error_to_http_status(exc: Exception) -> int:
    """Map an authorization failure to an HTTP status code.

    A missing tenant claim is an authentication defect (401 -- the credential
    is insufficient for the operation); a mismatched tenant is a genuine
    authorization denial (403).
    """
    message = str(exc)
    if "could not be derived" in message:
        return 401
    return 403


__all__ = [
    "TENANT_ID_MAX_LENGTH",
    "auth_error_to_http_status",
    "resolve_tenant_id",
    "validate_tenant_id",
]
