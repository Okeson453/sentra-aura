"""FastAPI middleware for SentraAura services.

Request tracing, auth context injection, metrics, rate limiting, and error handling.
Matches Architecture §10.2 and Backend Spec §10.
"""
from __future__ import annotations

import importlib
import logging
import time
import uuid
from typing import Any, Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
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


#: Service ``db.base`` modules that expose the tenant RLS primitives
#: (``set_tenant_context`` / ``reset_tenant_context`` / ``get_tenant_context``).
#: A service imports one of these; the module installs a SQLAlchemy
#: ``do_orm_execute`` listener that injects a tenant predicate into every
#: SELECT against a model carrying a ``tenant_id`` column.
RLS_DB_BASE_MODULES: tuple[str, ...] = (
    "control_plane_api.db.base",
    "asset_store.db.base",
    "content_graph_service.db.base",
    "data_ingestion_pipeline.db.base",
    "orchestrator.db.base",
    "policy_engine.db.base",
    "media_renderer.db.base",
)


class TenantResolutionMiddleware(BaseHTTPMiddleware):
    """Resolve the acting tenant from the VERIFIED authentication context.

    Tenant identity is a security boundary, so it may only come from the
    verified JWT claim.  An earlier revision read ``X-Tenant-ID`` (and a
    ``/tenants/<id>`` path segment) and published that straight onto
    ``request.state.tenant_id``: any caller holding a token for tenant-a
    could act as tenant-b by setting one header, and because the ORM
    row-level-security context is derived from this value, the tenant they
    could read was widened by the request itself.

    A client-supplied tenant is still parsed -- but only so it can be
    *verified* as an assertion against the authenticated claim.  A mismatch is
    logged as a ``tenant_isolation_violation`` and the authenticated tenant is
    used regardless.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        asserted = request.headers.get("X-Tenant-ID") or request.query_params.get("tenant_id")
        auth_context = getattr(request.state, "auth_context", None)
        token_tenant = getattr(auth_context, "tenant_id", None) if auth_context else None

        if token_tenant:
            if asserted and asserted.strip() != token_tenant:
                logger.warning(
                    "tenant_isolation_violation: caller asserted a tenant that does "
                    "not match the verified token claim",
                    extra={"asserted_tenant": asserted.strip(), "token_tenant": token_tenant},
                )
            request.state.tenant_id = token_tenant
        else:
            # No authenticated tenant: withhold the context rather than invent
            # one. A route that needs a tenant must reject the request.
            request.state.tenant_id = None
        return await call_next(request)


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Arm the ORM row-level-security hook for the duration of a request.

    Each service's ``db/base.py`` installs a ``do_orm_execute`` listener that
    injects a tenant predicate into every SELECT against a model with a
    ``tenant_id`` column -- but only while a tenant is set on the context var.
    Nothing in production ever called ``set_tenant_context``, so that control
    was dead code and every ORM query ran unscoped.  This middleware sets it
    from the verified claim and resets it in ``finally``, so a pooled
    connection or reused task can never inherit another tenant's scope.

    When isolation is enabled but no RLS module is importable, that gap is
    logged once per process so it is visible rather than silent.
    """

    def __init__(self, app: Any, *, enabled: bool = True) -> None:
        super().__init__(app)
        self.enabled = enabled
        self._warned: set[str] = set()

    @staticmethod
    def _load_primitives() -> list[tuple[str, Any, Any]]:
        primitives: list[tuple[str, Any, Any]] = []
        for name in RLS_DB_BASE_MODULES:
            try:
                module = importlib.import_module(name)
            except Exception:
                continue
            setter = getattr(module, "set_tenant_context", None)
            resetter = getattr(module, "reset_tenant_context", None)
            if setter is not None and resetter is not None:
                primitives.append((name, setter, resetter))
        return primitives

    def _warn_once(self, key: str, message: str) -> None:
        if key not in self._warned:
            self._warned.add(key)
            logger.warning(message)

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if not self.enabled:
            return await call_next(request)
        tenant_id = getattr(request.state, "tenant_id", None)
        if not tenant_id:
            return await call_next(request)

        primitives = self._load_primitives()
        if not primitives:
            self._warn_once(
                "no-rls-module",
                "tenant isolation is enabled but no RLS-enabled db.base module is "
                "importable in this process; ORM queries will not be tenant-scoped",
            )
            return await call_next(request)

        armed: list[tuple[Any, Any]] = []
        for name, setter, resetter in primitives:
            try:
                armed.append((resetter, setter(tenant_id)))
            except Exception:
                self._warn_once(f"arm-failed:{name}", f"failed to arm tenant context for {name}")
        try:
            return await call_next(request)
        finally:
            for resetter, token in armed:
                try:
                    resetter(token)
                except Exception:
                    logger.warning("failed to reset tenant context", exc_info=True)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Extract and validate JWT, inject auth context into request state."""

    def __init__(self, app: Any, *, jwt_secret: str | None = None, jwt_algorithm: str = "HS256", require_auth: bool = False) -> None:
        super().__init__(app)
        self.jwt_secret = jwt_secret
        self.jwt_algorithm = jwt_algorithm
        self.require_auth = require_auth
        self._exempt_paths = {"/health", "/ready", "/metrics"}

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        from sentinel_security import authenticate_request, AuthContext
        from sentinel_security.auth import AuthenticationError

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                auth_context = authenticate_request(
                    token,
                    jwt_secret=self.jwt_secret,
                    jwt_algorithms=[self.jwt_algorithm],
                )
                request.state.auth_context = auth_context
                request.state.auth_token = token
                request.state.authenticated = True
            except AuthenticationError as exc:
                logger.warning(f"Auth validation failed: {exc}")
                request.state.authenticated = False
                request.state.auth_error = str(exc)
                if self.require_auth and request.url.path not in self._exempt_paths:
                    return JSONResponse(
                        status_code=401,
                        content={"error_code": "UNAUTHENTICATED", "message": "Invalid or expired token"},
                    )
        else:
            request.state.authenticated = False
            if self.require_auth and request.url.path not in self._exempt_paths:
                return JSONResponse(
                    status_code=401,
                    content={"error_code": "UNAUTHENTICATED", "message": "Authorization header required"},
                )
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


def setup_middleware(
    app: Any,
    *,
    jwt_secret: str | None = None,
    jwt_algorithm: str = "HS256",
    require_auth: bool | None = None,
    enforce_tenant_isolation: bool | None = None,
) -> None:
    """Register all standard SentraAura middleware on a FastAPI app.

    Authentication posture is read from configuration when not passed
    explicitly and **defaults to requiring authentication**. ``require_auth``
    previously defaulted to False, so a service became fail-open simply by
    calling ``setup_middleware(app)`` -- the omission was silent and every
    route was served to unauthenticated callers. A deployment that genuinely
    intends an open surface now opts out explicitly (``REQUIRE_AUTH=false`` or
    ``require_auth=False``), so the posture is always a visible decision.

    When ``require_auth`` is True, requests to non-exempt paths (all paths
    except /health, /ready, /metrics) without a valid JWT are rejected with
    401 by AuthenticationMiddleware.

    ``enforce_tenant_isolation`` additionally arms the ORM row-level-security
    hook for the duration of each authenticated request (see
    TenantContextMiddleware).
    """
    from service_kit.config import ServiceConfig

    config = ServiceConfig()
    if jwt_secret is None:
        jwt_secret = config.jwt_secret
    if require_auth is None:
        require_auth = config.require_auth
    if enforce_tenant_isolation is None:
        enforce_tenant_isolation = config.enforce_tenant_isolation

    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(TracingMiddleware)
    # Added before TenantResolutionMiddleware so it runs *after* it (Starlette
    # applies middleware in reverse registration order).
    app.add_middleware(TenantContextMiddleware, enabled=enforce_tenant_isolation)
    app.add_middleware(TenantResolutionMiddleware)
    app.add_middleware(
        AuthenticationMiddleware,
        jwt_secret=jwt_secret,
        jwt_algorithm=jwt_algorithm,
        require_auth=require_auth,
    )
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(ErrorHandlingMiddleware)
    app.add_middleware(TimingMiddleware)
