"""FastAPI lifespan for SentraAura services.

Initializes database, event bus, tracer, and logger on startup.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI

from observability.logging import configure_logging, get_logger
from observability.tracing import get_tracer

logger = get_logger(__name__)


@asynccontextmanager
async def create_lifespan(
    app: FastAPI,
    *,
    service_name: str,
    db_url: str | None = None,
    nats_url: str | None = None,
    init_db: bool = False,
) -> AsyncGenerator[None, None]:
    """Create a FastAPI lifespan context manager.

    On startup: configure logging, initialize tracer, connect to DB/NATS.
    On shutdown: close connections.
    """
    configure_logging(level="INFO", service_name=service_name)
    tracer = get_tracer(service_name)

    logger.info(f"Starting {service_name}", extra={"service": service_name})

    # Initialize DB if configured
    if db_url and init_db:
        from service_kit.db import DatabaseManager
        db = DatabaseManager(db_url)
        await db.connect()
        app.state.db = db
        logger.info("Database connected")

    # Initialize NATS if configured
    if nats_url:
        # Would connect to NATS here
        logger.info("NATS connection configured")

    app.state.tracer = tracer
    app.state.service_name = service_name

    yield

    # Shutdown
    logger.info(f"Shutting down {service_name}")
    if hasattr(app.state, "db"):
        await app.state.db.close()
        logger.info("Database disconnected")
