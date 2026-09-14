"""Authentication utilities for SentraAura services.

Supports JWT validation for human users (Auth0/OIDC) and
service-account JWTs for inter-service/agent auth.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from jwt.exceptions import InvalidTokenError

from sentinel_exceptions import AuthenticationError


class AuthContext:
    """Parsed authentication context for a request."""

    def __init__(
        self,
        subject: str,
        subject_type: str,  # "human" | "service" | "agent"
        roles: list[str],
        channel_ids: list[str] | None = None,
        claims: dict[str, Any] | None = None,
        tenant_id: str | None = None,
    ) -> None:
        self.subject = subject
        self.subject_type = subject_type
        self.roles = roles
        self.channel_ids = channel_ids or []
        self.claims = claims or {}
        #: The tenant this principal is bound to, taken from the *verified*
        #: token. This is the only trusted source of tenant identity; request
        #: headers, query parameters and bodies are treated as untrusted
        #: assertions (see sentinel_security.tenant).
        self.tenant_id: str | None = (
            tenant_id
            or self.claims.get("tenant_id")
            or self.claims.get("org_id")
        )


def authenticate_request(
    token: str,
    *,
    jwt_secret: str | None = None,
    jwt_algorithms: list[str] | None = None,
    audience: str | None = None,
    issuer: str | None = None,
) -> AuthContext:
    """Validate a JWT and return an AuthContext.

    Raises AuthenticationError on any validation failure.
    Fails closed: if no jwt_secret is provided, signature verification is required.
    """
    algorithms = jwt_algorithms or ["RS256", "HS256"]

    # Fail closed: if no secret provided for HS256, require RS256 or fail
    if jwt_secret is None and "HS256" in algorithms:
        # Remove HS256 from allowed algorithms if no secret
        algorithms = [a for a in algorithms if a != "HS256"]
        if not algorithms:
            raise AuthenticationError("No JWT secret provided and no valid algorithms available")

    try:
        payload = jwt.decode(
            token,
            jwt_secret or "",
            algorithms=algorithms,
            audience=audience,
            issuer=issuer,
            options={"verify_signature": True},
        )
    except InvalidTokenError as exc:
        raise AuthenticationError(f"Invalid token: {exc}") from exc

    subject = payload.get("sub", "")
    subject_type = payload.get("type", "human")
    roles = payload.get("roles", [])
    channel_ids = payload.get("channel_ids", [])

    return AuthContext(
        subject=subject,
        subject_type=subject_type,
        roles=roles,
        channel_ids=channel_ids,
        claims=payload,
    )


def create_service_token(
    service_name: str,
    roles: list[str],
    *,
    secret: str,
    ttl_seconds: int = 3600,
    algorithm: str = "HS256",
    tenant_id: str | None = None,
) -> str:
    """Create a short-lived service-account JWT.

    ``tenant_id`` binds the resulting credential to a single tenant. Services
    use it to scope every data access to the tenant that the token authorises,
    so a caller can never widen its own blast radius by naming another tenant
    in a payload.
    """
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": f"service:{service_name}",
        "type": "service",
        "roles": roles,
        "iat": now,
        "exp": now + timedelta(seconds=ttl_seconds),
    }
    if tenant_id:
        payload["tenant_id"] = tenant_id
    return jwt.encode(payload, secret, algorithm=algorithm)
