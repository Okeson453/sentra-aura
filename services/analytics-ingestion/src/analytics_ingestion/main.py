"""FastAPI application for the Analytics Ingestion Service."""
from __future__ import annotations

import hmac
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

from service_kit.middleware import setup_middleware

from analytics_ingestion.background_tasks import BackgroundTaskScheduler
from analytics_ingestion.config import config
from analytics_ingestion.consumers import (
    DURABLE_NAME,
    PUBLICATION_PUBLISHED_SUBJECT,
    start_publication_consumer,
    tracker,
)
from analytics_ingestion.normalization import NormalizedMetrics, normalize_metrics, compute_performance_signal
from analytics_ingestion.warehouse_writer import WarehouseWriter
from analytics_ingestion.youtube_analytics_client import YouTubeAnalyticsClient

logger = logging.getLogger(__name__)
writer = WarehouseWriter(
    warehouse_url=config.warehouse_url,
    batch_size=config.batch_size,
    flush_interval_seconds=config.flush_interval_seconds,
)
yt_client = YouTubeAnalyticsClient(api_key=config.youtube_api_key)
scheduler = BackgroundTaskScheduler(
    youtube_client=yt_client,
    warehouse_writer=writer,
    channel_ids=list(config.channel_ids),
    fetch_interval_seconds=config.video_metrics_fetch_interval_seconds,
    flush_interval_seconds=config.flush_interval_seconds,
    health_check_interval_seconds=config.channel_health_check_interval_seconds,
    max_videos_per_fetch=config.max_videos_per_channel_fetch,
)

# Runtime state for the feedback consumer. Reported verbatim by /api/v1/tasks/status
# so a deployment can tell the difference between "consuming feedback" and
# "the loop is silently open".
_consumer_state: dict[str, Any] = {
    "status": "stopped",
    "subject": PUBLICATION_PUBLISHED_SUBJECT,
    "durable": DURABLE_NAME,
    "error": None,
}
_nats_client: Any = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _nats_client
    await writer.start()
    if config.enable_background_ingestion:
        await scheduler.start()
    try:
        _nats_client, _consumer = await start_publication_consumer()
        _consumer_state.update(status="running", error=None)
    except Exception as exc:  # never claim feedback we do not have
        _consumer_state.update(status="failed", error=str(exc))
        logger.error("analytics feedback consumer failed to start: %s", exc, exc_info=True)
    logger.info("Analytics Ingestion Service started")
    yield
    if config.enable_background_ingestion:
        await scheduler.stop()
    if _nats_client is not None:
        try:
            await _nats_client.close()
        except Exception as exc:
            logger.warning("NATS client close failed: %s", exc)
    await writer.stop()
    await yt_client.close()
    logger.info("Analytics Ingestion Service stopped")


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
