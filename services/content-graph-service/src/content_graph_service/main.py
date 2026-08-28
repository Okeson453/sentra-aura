"""FastAPI service for the Content Asset Graph."""
from __future__ import annotations

from fastapi import FastAPI
from service_kit.health import health_router
from service_kit.middleware import setup_middleware
from content_graph_service.routes import router

app = FastAPI(title="SentraAura Content Asset Graph", version="0.1.0")
setup_middleware(app)
app.include_router(health_router, tags=["Health"])
app.include_router(router, prefix="/api/v1")
