"""FastAPI service for the Content Asset Graph."""
from __future__ import annotations

from fastapi import FastAPI
from service_kit.health import health_router
from service_kit.middleware import setup_middleware
from content_graph_service.config import get_settings
from content_graph_service.routes import router

settings = get_settings()

app = FastAPI(title="SentraAura Content Asset Graph", version="0.1.0")
# Authentication is enforced at the app boundary: every route previously ran
# with setup_middleware(app) and a fail-open require_auth default, so the
# lineage graph was readable and mutable without any credential.
setup_middleware(
    app,
    jwt_secret=settings.jwt_secret,
    jwt_algorithm=settings.jwt_algorithm,
    require_auth=True,
    enforce_tenant_isolation=getattr(settings, "enforce_tenant_isolation", True),
)
app.include_router(health_router, tags=["Health"])
app.include_router(router, prefix="/api/v1")
