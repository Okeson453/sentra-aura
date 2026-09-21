"""FastAPI service for the Orchestrator."""
from __future__ import annotations

from fastapi import FastAPI
from service_kit.health import health_router
from service_kit.middleware import setup_middleware

from orchestrator.config import get_settings
from orchestrator.registry import ALL_ACTIVITIES, ALL_WORKFLOWS

settings = get_settings()

# Re-export registration for process launchers and deployment introspection.
__all__ = ["ALL_ACTIVITIES", "ALL_WORKFLOWS", "app"]

app = FastAPI(title="SentraAura Orchestrator", version="0.1.0")
# Authentication is enforced at the app boundary instead of relying on the
# middleware's (now fail-closed) default and on every route remembering to
# declare an auth dependency.
setup_middleware(
    app,
    jwt_secret=settings.jwt_secret,
    jwt_algorithm=settings.jwt_algorithm,
    require_auth=True,
    enforce_tenant_isolation=getattr(settings, "enforce_tenant_isolation", True),
)
app.include_router(health_router, tags=["Health"])
