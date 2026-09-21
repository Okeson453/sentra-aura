"""FastAPI service for the Asset Store."""
from __future__ import annotations

from fastapi import FastAPI
from service_kit.health import health_router
from service_kit.middleware import setup_middleware
from asset_store.config import get_settings
from asset_store.routes import router

settings = get_settings()

app = FastAPI(title="SentraAura Asset Store", version="0.1.0")
# Authentication is enforced at the app boundary: every route previously ran
# with setup_middleware(app) and a fail-open require_auth default, so this
# asset store served and mutated objects for callers that presented no
# credential at all.
setup_middleware(
    app,
    jwt_secret=settings.jwt_secret,
    jwt_algorithm=settings.jwt_algorithm,
    require_auth=True,
    enforce_tenant_isolation=getattr(settings, "enforce_tenant_isolation", True),
)
app.include_router(health_router, tags=["Health"])
app.include_router(router, prefix="/api/v1")
