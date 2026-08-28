"""FastAPI dependencies for control-plane-api.

Provides DB sessions, auth, caching, rate limiting, and tenant resolution.
Matches Architecture §3.1 and Backend Spec §3.
"""
from __future__ import annotations

from typing import Any, AsyncGenerator, Generator
from functools import lru_cache

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from control_plane_api.config import get_settings
from control_plane_api.db.session import get_db, get_async_db

settings = get_settings()
security = HTTPBearer(auto_error=False)


async def get_current_tenant(request: Request) -> str:
    """Resolve tenant from header, query param, or path."""
    tenant = (
        request.headers.get("X-Tenant-ID")
        or request.query_params.get("tenant_id")
        or request.path_params.get("tenant_id")
    )
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant ID required",
        )
    if settings.allowed_tenants and tenant not in settings.allowed_tenants:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant not authorized",
        )
    return tenant


async def get_current_channel(request: Request) -> str:
    """Resolve channel from header, query param, or path."""
    channel = (
        request.headers.get("X-Channel-ID")
        or request.query_params.get("channel_id")
        or request.path_params.get("channel_id")
    )
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Channel ID required",
        )
    return channel


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    """Verify API key from Authorization header."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # In production: validate against secrets manager
    if credentials.credentials != settings.jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self) -> None:
        self._requests: dict[str, list[float]] = {}

    def is_allowed(self, key: str) -> bool:
        import time
        now = time.time()
        window = settings.rate_limit_window_seconds
        max_req = settings.rate_limit_requests

        reqs = self._requests.get(key, [])
        reqs = [r for r in reqs if now - r < window]
        self._requests[key] = reqs

        if len(reqs) >= max_req:
            return False
        reqs.append(now)
        return True


_rate_limiter = RateLimiter()


async def rate_limit(request: Request) -> None:
    """Rate limit dependency."""
    key = f"{request.client.host}:{request.url.path}"
    if not _rate_limiter.is_allowed(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(settings.rate_limit_window_seconds)},
        )


def get_db_session() -> Generator[Session, None, None]:
    """Synchronous DB session dependency."""
    yield from get_db()


async def get_async_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Async DB session dependency."""
    async for session in get_async_db():
        yield session


async def get_cache() -> Any:
    """Return cache client if configured."""
    if settings.redis_url:
        # In production: return redis client
        pass
    return None
