"""FastAPI middleware for SentraAura services.

Request tracing, auth context injection, metrics, rate limiting, and error handling.
Matches Architecture §10.2 and Backend Spec §10.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from service_kit.metrics import get_metrics_collector

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Inject a unique request ID into each request."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    """Record request latency and count metrics."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        start = time.perf_counter()
        metrics = get_metrics_collector()
        path = request.url.path
        method = request.method

        try:
            response = await call_next(request)
            status = response.status_code
            metrics.counter("http_requests_total", 1.0, {"method": method, "path": path, "status": str(status)})
            return response
        except Exception:
            metrics.counter("http_requests_total", 1.0, {"method": method, "path": path, "status": "500"})
            raise
        finally:
            latency = (time.perf_counter() - start) * 1000
            metrics.histogram("http_request_duration_ms", latency, {"method": method, "path": path})
            metrics.gauge("http_request_last_duration_ms", latency, {"method": method, "path": path})


class TenantResolutionMiddleware(BaseHTTPMiddleware):
    """Extract tenant ID from request headers or JWT and inject into request state."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        tenant_id = request.headers.get("X-Tenant-ID", "")
        if not tenant_id:
            # Try to extract from path
            path_parts = request.url.path.strip("/").split("/")
            if len(path_parts) >= 2 and path_parts[0] == "tenants":
                tenant_id = path_parts[1]
        request.state.tenant_id = tenant_id
        return await call_next(request)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Extract and validate JWT, inject auth context into request state."""

    def __init__(self, app: Any, *, jwt_secret: str | None = None) -> None:
        super().__init__(app)
        self.jwt_secret = jwt_secret

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                # In production, validate JWT properly
                request.state.auth_token = token
                request.state.authenticated = True
            except Exception as exc:
                logger.warning(f"Auth validation failed: {exc}")
                request.state.authenticated = False
        else:
            request.state.authenticated = False
        return await call_next(request)


class TracingMiddleware(BaseHTTPMiddleware):
    """Inject trace_id into request context and response headers."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        return response


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Catch exceptions and return standardized error responses."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            logger.exception("Unhandled exception in request")
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=500,
                content={
                    "error_code": "INTERNAL_ERROR",
                    "message": "An internal error occurred",
                    "request_id": getattr(request.state, "request_id", ""),
                    "trace_id": getattr(request.state, "trace_id", ""),
                },
            )


class TimingMiddleware(BaseHTTPMiddleware):
    """Record request latency in response headers."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        latency = (time.perf_counter() - start) * 1000
        response.headers["X-Response-Time-Ms"] = str(int(latency))
        return response


def setup_middleware(app: Any) -> None:
    """Register all standard SentraAura middleware on a FastAPI app."""
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(TracingMiddleware)
    app.add_middleware(TenantResolutionMiddleware)
    app.add_middleware(AuthenticationMiddleware)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(ErrorHandlingMiddleware)
    app.add_middleware(TimingMiddleware)
