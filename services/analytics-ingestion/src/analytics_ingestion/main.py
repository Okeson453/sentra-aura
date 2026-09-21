"""Analytics Ingestion Service — FastAPI application.

Ingests, normalizes and persists YouTube performance data, and closes the
feedback half of the operating loop by consuming ``publication.published``.
"""
from __future__ import annotations

import hmac
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

from service_kit.middleware import setup_middleware

from analytics_ingestion.background_tasks import scheduler
from analytics_ingestion.config import config
from analytics_ingestion.consumers import
    PUBLICATION_PUBLISHED_SUBJECT,
    DURABLE_NAME,
    tracker,

logger = logging.getLogger(__name__)


_consumer_state: dict[str, Any] = {
    "status": "not_started",
    "subject": PUBLICATION_PUBLISHED_SUBJECT,
    "durable_name": DURABLE_NAME,
    "error": None,
}


def _record_consumer_state(status: str, error: str | None = None) -> None:
    _consumer_state["status"] = status
    _consumer_state["error"] = error
    _consumer_state["updated_at"] = datetime.now(timezone.utc).isoformat()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the feedback consumer and the periodic fetch, and stop them cleanly."""
    nats_client = None
    try:
        from analytics_ingestion.consumers import start_publication_consumer

        nats_client, _consumer = await start_publication_consumer()
        _record_consumer_state("running")
    except Exception as exc:  # pragma: no cover - depends on broker availability
        logger.error("Failed to start publication consumer: %s", exc)
        _record_consumer_state("failed", str(exc))

    if config.enable_background_ingestion:
        try:
            await scheduler.start()
        except Exception as exc:  # pragma: no cover
            logger.error("Failed to start background ingestion: %s", exc)

    yield

    await scheduler.stop()
    if nats_client is not None:
        try:
            await nats_client.close()
        except Exception as exc:  # pragma: no cover
            logger.warning("Error closing NATS client: %s", exc)


app = FastAPI(
    title="Analytics Ingestion Service",
    version="1.0.0",
    description="Ingests, normalizes, and writes YouTube Analytics data to the warehouse.",
    lifespan=lifespan,
)

# Authentication is enforced at the application boundary, not per route: before
# this the service called no middleware setup at all, so *every* route served
# unauthenticated callers while handling tenant-sensitive performance data and
# driving provider quota. Registering it here means a route added later cannot
# be left open by omission.
setup_middleware(
    app,
    jwt_secret=config.jwt_secret,
    jwt_algorithm=config.jwt_algorithm,
    require_auth=config.require_auth,
)


def _acting_tenant(request: Request) -> str:
    """The tenant proven by the request's verified authentication context.

    ``request.state.tenant_id`` is published by the shared middleware from the
    verified JWT claim only (never a client-supplied header), so it is the one
    trustworthy source of tenant identity in this process.
    """
    tenant = getattr(request.state, "tenant_id", None)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="no authenticated tenant context for this request",
        )
    return str(tenant)


def _verify_tenant_assertion(request: Request, asserted: str | None) -> str:
    """Verify an optional caller-supplied tenant against the authenticated one.

    A body/query tenant is treated purely as an assertion to be checked, never
    as the source of identity. A mismatch is a rejected cross-tenant request.
    """
    acting = _acting_tenant(request)
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


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "service": config.service_name}


@app.get("/ready")
async def ready() -> dict[str, Any]:
    return {
        "status": "ready",
        "feedback_consumer": dict(_consumer_state),
    }


@app.get("/api/v1/tasks/status")
async def get_task_status() -> dict[str, Any]:
    """Report the real state of background tasks and the feedback consumer."""
    return {
        "tasks": scheduler.status(),
        "feedback_consumer": dict(_consumer_state),
    }
