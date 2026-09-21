"""FastAPI service for the Policy Engine.

Authentication is enforced here rather than left to each handler.  The previous
configuration called ``setup_middleware(app)`` with no JWT settings, which takes
``require_auth=False``: ``GET /api/v1/policies/{channel_id}`` served policy data
to any caller that sent no credential at all.

The secret is read from ``JWT_SECRET`` via ``policy_engine.config.get_settings``.
In an environment that is not ``development``/``test`` the settings validator
rejects the insecure placeholder, so the service fails to start rather than
silently accepting tokens signed with a well-known value.
"""
from __future__ import annotations

from fastapi import FastAPI
from service_kit.health import health_router
from service_kit.middleware import setup_middleware

from policy_engine.config import get_settings
from policy_engine.routes import router

settings = get_settings()

app = FastAPI(title="SentraAura Policy Engine", version="0.1.0")
setup_middleware(
    app,
    jwt_secret=settings.jwt_secret,
    jwt_algorithm=settings.jwt_algorithm,
    require_auth=True,
)
app.include_router(health_router, tags=["Health"])
app.include_router(router, prefix="/api/v1")
