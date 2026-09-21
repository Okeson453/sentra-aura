"""FastAPI application for the Analytics Ingestion Service.

The application object is assembled here from small route modules so each unit
stays reviewable; the process-wide singletons live in ``runtime``.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette import status

from service_kit.middleware import setup_middleware

from analytics_ingestion import runtime
from analytics_ingestion.config import config
from analytics_ingestion.consumers import start_publication_consumer
from analytics_ingestion.routes_feedback import router as feedback_router
from analytics_ingestion.routes_metrics import router as metrics_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await runtime.writer.start()
    if config.enable_background_ingestion:
        await runtime.scheduler.start()
    try:
        runtime.nats_client, _consumer = await start_publication_consumer()
        runtime.consumer_state.update(status="running", error=None)
    except Exception as exc:  # never claim feedback we do not have
        runtime.consumer_state.update(status="failed", error=str(exc))
        logger.error("analytics feedback consumer failed to start: %s", exc, exc_info=True)
    logger.info("Analytics Ingestion Service started")
    yield
    if config.enable_background_ingestion:
        await runtime.scheduler.stop()
    if runtime.nats_client is not None:
        try:
            await runtime.nats_client.close()
        except Exception as exc:
            logger.warning("NATS client close failed: %s", exc)
    await runtime.writer.stop()
    await runtime.yt_client.close()
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

app.include_router(metrics_router)
app.include_router(feedback_router)


@app.get("/health")
async def health_check() -> dict:
    return {"status": "healthy", "service": config.service_name}


@app.get("/ready")
async def readiness_check() -> dict:
    return {"status": "ready", "service": config.service_name}


@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error_code": "VALIDATION_ERROR", "message": str(exc)},
    )
