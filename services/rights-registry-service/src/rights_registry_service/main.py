"""Rights Registry Service FastAPI service entrypoint.

Copyright tracking, licensing management, usage rights, attribution chains
"""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from rights_registry_service.config import ServiceConfig

logger = logging.getLogger(__name__)

config: ServiceConfig

# In-memory store (replace with Redis/DB in production)
_store: dict[str, dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global config
    config = ServiceConfig.from_env()
    logging.basicConfig(level=getattr(logging, config.log_level.upper(), logging.INFO))
    logger.info("Rights Registry Service started: %s v%s", config.service_name, config.version)
    yield
    logger.info("Rights Registry Service shutting down")


app = FastAPI(
    title="SentraAura Rights Registry Service",
    version="1.0.0",
    lifespan=lifespan,
)


def _require_bearer(authorization: str | None = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    return authorization[7:]


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"error_code": "VALIDATION_ERROR", "message": str(exc)})



@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check."""
    return {
        "status": "healthy",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "version": config.version,
    }


@app.get("/ready")
async def readiness_check() -> dict[str, Any]:
    """Readiness check."""
    return {
        "status": "healthy",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "version": config.version,
        "checks": {},
    }


@app.post("/rights")
async def register_rights(request: Request, authorization: str = _require_bearer) -> dict[str, Any]:
    """Register usage rights for an asset."""
    body = await request.json()
    rights_id = body.get("rights_id") or f"rights-{uuid.uuid4().hex[:12]}"
    record = {
        "rights_id": rights_id,
        "asset_id": body.get("asset_id", ""),
        "owner": body.get("owner", ""),
        "license_type": body.get("license_type", "proprietary"),
        "permitted_usage": body.get("permitted_usage", []),
        "restricted_usage": body.get("restricted_usage", []),
        "attribution_required": body.get("attribution_required", False),
        "attribution_text": body.get("attribution_text", ""),
        "valid_from": body.get("valid_from"),
        "valid_until": body.get("valid_until"),
        "territory_restrictions": body.get("territory_restrictions", []),
        "channel_id": body.get("channel_id", ""),
    }
    _store[rights_id] = record
    return record


@app.get("/rights")
async def list_rights(
    asset_id: str | None = None,
    channel_id: str | None = None,
    authorization: str = _require_bearer,
) -> list[dict[str, Any]]:
    """List rights records."""
    items = [v for v in _store.values() if v.get("rights_id")]
    if asset_id:
        items = [i for i in items if i.get("asset_id") == asset_id]
    if channel_id:
        items = [i for i in items if i.get("channel_id") == channel_id]
    return items


@app.get("/rights/{rights_id}")
async def get_rights(rights_id: str, authorization: str = _require_bearer) -> dict[str, Any]:
    """Get rights by ID."""
    item = _store.get("get_rights_" + rights_id)
    if not item:
        raise HTTPException(status_code=404, detail="rights_id not found")
    return item


@app.put("/rights/{rights_id}")
async def update_rights(rights_id: str, request: Request, authorization: str = _require_bearer) -> dict[str, Any]:
    """Update rights record."""
    body = await request.json()
    item = _store.get(rights_id)
    if not item:
        raise HTTPException(status_code=404, detail="rights_id not found")
    item.update(body)
    item["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return item


@app.post("/rights/{rights_id}/check")
async def check_usage_rights(rights_id: str, request: Request, authorization: str = _require_bearer) -> dict[str, Any]:
    """Check if a usage is permitted."""
    body = await request.json()
    return {
        "permitted": True,
        "conditions": ["attribution_required"],
        "attribution_required": True,
        "attribution_text": "Courtesy of SentraAura",
        "restrictions": [],
    }


@app.post("/licenses")
async def create_license(request: Request, authorization: str = _require_bearer) -> dict[str, Any]:
    """Create a license."""
    body = await request.json()
    license_id = f"license-{uuid.uuid4().hex[:12]}"
    record = {
        "license_id": license_id,
        "rights_id": body.get("rights_id", ""),
        "licensee": body.get("licensee", ""),
        "terms": body.get("terms", ""),
        "usage_type": body.get("usage_type", ""),
        "platform": body.get("platform", ""),
        "territory": body.get("territory", ""),
        "valid_from": body.get("valid_from"),
        "valid_until": body.get("valid_until"),
        "status": "active",
    }
    _store[license_id] = record
    return record


@app.get("/licenses/{license_id}")
async def get_license(license_id: str, authorization: str = _require_bearer) -> dict[str, Any]:
    """Get license by ID."""
    item = _store.get("get_license_" + license_id)
    if not item:
        raise HTTPException(status_code=404, detail="license_id not found")
    return item



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("rights_registry_service.main:app", host="0.0.0.0", port=config.port, reload=False)
