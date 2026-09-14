"""FastAPI service for the Orchestrator."""
from __future__ import annotations

from fastapi import FastAPI
from service_kit.health import health_router
from service_kit.middleware import setup_middleware

from orchestrator.registry import ALL_ACTIVITIES, ALL_WORKFLOWS

# Re-export registration for process launchers and deployment introspection.
__all__ = ["ALL_ACTIVITIES", "ALL_WORKFLOWS", "app"]

app = FastAPI(title="SentraAura Orchestrator", version="0.1.0")
setup_middleware(app)
app.include_router(health_router, tags=["Health"])
