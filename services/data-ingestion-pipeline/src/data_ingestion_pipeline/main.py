"""FastAPI service for the Data Ingestion Pipeline."""
from __future__ import annotations

from fastapi import FastAPI
from service_kit.health import HealthStatus, _registry, health_router
from service_kit.middleware import setup_middleware
from data_ingestion_pipeline.routes import publisher, router


async def _nats_readiness() -> tuple[HealthStatus, float]:
    """Report whether the configured publisher can currently accept events."""
    status = HealthStatus.HEALTHY if publisher.is_ready else HealthStatus.UNHEALTHY
    return status, 0.0


_registry.register("nats", _nats_readiness)

app = FastAPI(title="SentraAura Data Ingestion Pipeline", version="0.1.0")
setup_middleware(app)
app.include_router(health_router, tags=["Health"])
app.include_router(router, prefix="/api/v1")
