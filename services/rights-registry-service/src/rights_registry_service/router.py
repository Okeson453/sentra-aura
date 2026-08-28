"""API route handlers for rights and license endpoints.

Separates routing logic from main.py for testability.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from typing import Any

from rights_registry_service.models import RightsRegistrationRequest, RightsUpdateRequest, LicenseCreateRequest, UsageCheckRequest
from rights_registry_service.service import RightsRegistryService

router = APIRouter(tags=["rights"])
service = RightsRegistryService()


@router.post("/rights")
async def register_rights(request: RightsRegistrationRequest) -> dict[str, Any]:
    """Register usage rights for an asset."""
    return await service.register_rights(request)


@router.get("/rights")
async def list_rights(asset_id: str | None = None, channel_id: str | None = None) -> list[dict[str, Any]]:
    """List rights records."""
    return await service.list_rights(asset_id, channel_id)


@router.get("/rights/{rights_id}")
async def get_rights(rights_id: str) -> dict[str, Any]:
    """Get rights by ID."""
    record = await service.get_rights(rights_id)
    if not record:
        raise HTTPException(status_code=404, detail="Rights record not found")
    return record


@router.put("/rights/{rights_id}")
async def update_rights(rights_id: str, request: RightsUpdateRequest) -> dict[str, Any]:
    """Update rights record."""
    return await service.update_rights(rights_id, request)


@router.post("/rights/{rights_id}/check")
async def check_usage_rights(rights_id: str, request: UsageCheckRequest) -> dict[str, Any]:
    """Check if a usage is permitted."""
    return await service.check_usage(rights_id, request)


@router.post("/licenses")
async def create_license(request: LicenseCreateRequest) -> dict[str, Any]:
    """Create a license."""
    return await service.create_license(request)


@router.get("/licenses/{license_id}")
async def get_license(license_id: str) -> dict[str, Any]:
    """Get license by ID."""
    license = await service.get_license(license_id)
    if not license:
        raise HTTPException(status_code=404, detail="License not found")
    return license
