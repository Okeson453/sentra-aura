"""Tenant identity derived from the verified authentication context.

A caller-supplied tenant is never a source of identity here: it is only an
assertion to be checked against the tenant proven by the request's JWT. The
shared middleware publishes that verified tenant on ``request.state``; reading
it from a header, query parameter or path segment is what allowed a caller to
act as another tenant before the shared boundary was fixed.
"""
from __future__ import annotations

import hmac
import logging

from fastapi import HTTPException, Request, status

from analytics_ingestion.config import config

logger = logging.getLogger(__name__)


def acting_tenant(request: Request) -> str:
    """The tenant proven by the request's verified authentication context."""
    tenant = getattr(request.state, "tenant_id", None)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="no authenticated tenant context for this request",
        )
    return str(tenant)


def verify_tenant_assertion(request: Request, asserted: str | None) -> str:
    """Verify an optional caller-supplied tenant against the authenticated one.

    Returns the acting tenant. A mismatch is a rejected cross-tenant request;
    the comparison is constant-time so it cannot be used as an oracle.
    """
    acting = acting_tenant(request)
    if asserted and config.enforce_tenant_isolation:
        if not hmac.compare_digest(str(asserted), acting):
            logger.warning(
                "tenant_isolation_violation",
                extra={
                    "asserted_tenant": str(asserted),
                    "authenticated_tenant": acting,
                    "service": config.service_name,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="requested tenant does not match the authenticated tenant",
            )
    return acting
