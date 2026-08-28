"""FastAPI application for the Control Plane API."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from service_kit.config import Settings
from service_kit.health import health_router
from service_kit.lifespan import create_lifespan
from service_kit.middleware import setup_middleware

from control_plane_api.routes import (
    channels,
    content,
    publishing,
    analytics,
    experiments,
    policies,
    decisions,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield

    app = FastAPI(
        title="SentraAura Control Plane API",
        description="Configure, Observe, Inspect, Override, Analyze",
        version="0.1.0",
        lifespan=lifespan,
    )

    setup_middleware(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router, tags=["Health"])
    app.include_router(channels.router, prefix="/api/v1/channels", tags=["Channels"])
    app.include_router(content.router, prefix="/api/v1/content", tags=["Content"])
    app.include_router(publishing.router, prefix="/api/v1/publishing", tags=["Publishing"])
    app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
    app.include_router(experiments.router, prefix="/api/v1/experiments", tags=["Experiments"])
    app.include_router(policies.router, prefix="/api/v1/policies", tags=["Policies"])
    app.include_router(decisions.router, prefix="/api/v1/decisions", tags=["Decisions"])

    return app


app = create_app()
