"""FastAPI dependencies for policy-engine.

SECURITY: authentication and tenant derivation live here so no route can be
written without them.

``get_current_tenant`` resolves the acting tenant from the **verified** JWT
claim on ``request.state.auth_context`` via the shared enforcement point in
``sentinel_security.tenant``.  It never reads a client-supplied header, query
parameter or body -- the previous implementation did exactly that, so any
caller could name any tenant.

Performance: verifying the bearer token once per request is not free, so the
verified :class:`AuthContext` is cached on ``request.state`` and reused by
:func:`get_current_tenant`.
"""
from __future__ import annotations

from typing import Any, AsyncGenerator, Generator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from sentinel_exceptions import AuthorizationError
from sentinel_security import auth_error_to_http_status, resolve_tenant_id
from sentinel_security.auth import AuthenticationError, AuthContext, authenticate_request

from policy_engine.config import get_settings
from policy_engine.db.session import get_async_db, get_db

settings = get_settings()
security = HTTPBearer(auto_error=False)


def _verify_bearer(
    credentials: HTTPAuthorizationCredentials | None,
) -> AuthContext:
    """Validate a bearer token and return the resulting auth context."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return authenticate_request(
            credentials.credentials,
            jwt_secret=settings.jwt_secret,
            jwt_algorithms=[getattr(settings, "jwt_algorithm", "HS256")],
        )
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def verify_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> Any:
    """Verify the caller's JWT (dependency form).

    The result is memoised on ``request.state`` so a handler that also needs the
    tenant does not pay for a second signature verification.
    """
    auth_context = _verify_bearer(credentials)
    request.state.auth_context = auth_context
    return auth_context


async def get_current_tenant(request: Request) -> str:
    """Return the tenant the authenticated caller is allowed to act on.

    Raises 401 when the caller presented no usable credential and 403 when the
    credential carries no tenant binding or requests a tenant it does not own.
    """
    auth_context = getattr(request.state, "auth_context", None)
    if auth_context is None:
        # Middleware/enforcement may not have placed it on the request; verify
        # the bearer token ourselves so a route can never run unauthenticated.
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        token = auth_header[7:]
        try:
            auth_context = authenticate_request(
                token,
                jwt_secret=settings.jwt_secret,
                jwt_algorithms=[getattr(settings, "jwt_algorithm", "HS256")],
            )
        except AuthenticationError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {exc}",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        request.state.auth_context = auth_context

    try:
        tenant = resolve_tenant_id(
            auth_context,
            None,
            enforce_isolation=getattr(settings, "enforce_tenant_isolation", True),
        )
    except AuthorizationError as exc:
        raise HTTPException(
            status_code=auth_error_to_http_status(exc), detail=str(exc)
        ) from exc

    if settings.allowed_tenants and tenant not in settings.allowed_tenants:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant not authorized",
        )
    return tenant


async def get_current_channel(request: Request) -> str:
    """Resolve channel from the authenticated context's own request path/params."""
    channel = (
        request.query_params.get("channel_id")
        or request.path_params.get("channel_id")
    )
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Channel ID required",
        )
    return channel


class RateLimiter:
    """Simple in-process sliding-window rate limiter."""

    def __init__(self) -> None:
        self._requests: dict[str, list[float]] = {}

    def is_allowed(self, key: str) -> bool:
        import time

        now = time.time()
        window = settings.rate_limit_window_seconds
        max_req = settings.rate_limit_requests
        reqs = [r for r in self._requests.get(key, []) if now - r < window]
        self._requests[key] = reqs
        if len(reqs) >= max_req:
            return False
        reqs.append(now)
        return True


_rate_limiter = RateLimiter()


async def rate_limit(request: Request) -> None:
    key = f"{request.client.host}:{request.url.path}"
    if not _rate_limiter.is_allowed(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(settings.rate_limit_window_seconds)},
        )


def get_db_session() -> Generator[Session, None, None]:
    """Synchronous DB session dependency (sync generator -- not async)."""
    yield from get_db()


async def get_async_db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_async_db():
        yield session


async def get_cache() -> Any:
    return None
