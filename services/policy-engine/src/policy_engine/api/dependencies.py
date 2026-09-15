"""FastAPI dependencies for policy-engine."""
from __future__ import annotations

from typing import Any, AsyncGenerator, Generator

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from policy_engine.config import get_settings
from policy_engine.db.session import get_db, get_async_db

settings = get_settings()
security = HTTPBearer(auto_error=False)


async def get_current_tenant(request: Request) -> str:
    tenant = (
        request.headers.get("X-Tenant-ID")
        or request.query_params.get("tenant_id")
        or request.path_params.get("tenant_id")
    )
    if not tenant:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant ID required")
    if settings.allowed_tenants and tenant not in settings.allowed_tenants:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant not authorized")
    return tenant


async def get_current_channel(request: Request) -> str:
    channel = (
        request.headers.get("X-Channel-ID")
        or request.query_params.get("channel_id")
        or request.path_params.get("channel_id")
    )
    if not channel:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Channel ID required")
    return channel


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> Any:
    import hmac
    from sentinel_security import authenticate_request, AuthContext
    from sentinel_security.auth import AuthenticationError

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    try:
        return authenticate_request(
            token,
            jwt_secret=settings.jwt_secret,
            jwt_algorithms=[getattr(settings, "jwt_algorithm", "HS256")],
        )
    except AuthenticationError:
        pass
    expected = settings.jwt_secret or ""
    if expected and hmac.compare_digest(token.encode("utf-8"), expected.encode("utf-8")):
        return AuthContext(
            subject="service:static-key",
            subject_type="service",
            roles=["service"],
            claims={"auth_mode": "static_key"},
        )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


class RateLimiter:
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


async def get_db_session() -> Generator[Session, None, None]:
    yield from get_db()


async def get_async_db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_async_db():
        yield session


async def get_cache() -> Any:
    return None
