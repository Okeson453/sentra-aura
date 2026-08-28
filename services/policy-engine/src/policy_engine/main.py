"""FastAPI service for the Policy Engine."""
from __future__ import annotations

from fastapi import FastAPI
from service_kit.health import health_router
from service_kit.middleware import setup_middleware
from policy_engine.routes import router

app = FastAPI(title="SentraAura Policy Engine", version="0.1.0")
setup_middleware(app)
app.include_router(health_router, tags=["Health"])
app.include_router(router, prefix="/api/v1")
