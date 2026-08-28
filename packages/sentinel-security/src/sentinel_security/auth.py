"""Authentication utilities for SentraAura services.

Supports JWT validation for human users (Auth0/OIDC) and
service-account JWTs for inter-service/agent auth.
"""
from __future__ import annotations

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
    ) -> None:
        self.subject = subject
        self.subject_type = subject_type
        self.roles = roles
        self.channel_ids = channel_ids or []
        self.claims = claims or {}


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
    """
    algorithms = jwt_algorithms or ["RS256", "HS256"]
    try:
        payload = jwt.decode(
            token,
            jwt_secret or "",
            algorithms=algorithms,
            audience=audience,
            issuer=issuer,
            options={"verify_signature": bool(jwt_secret)},
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
) -> str:
    """Create a short-lived service-account JWT."""
    payload = {
        "sub": f"service:{service_name}",
        "type": "service",
        "roles": roles,
        "iat": jwt.utils.datetime_to_epoch(jwt.utils.get_int_from_datetime()),
        "exp": ttl_seconds,
    }
    return jwt.encode(payload, secret, algorithm=algorithm)
