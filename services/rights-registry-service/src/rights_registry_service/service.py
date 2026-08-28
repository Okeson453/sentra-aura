"""Business logic for rights registry and licensing.

Encapsulates all domain operations behind a service layer.
"""
from __future__ import annotations

import uuid
from typing import Any

from rights_registry_service.models import RightsRegistrationRequest, RightsUpdateRequest, LicenseCreateRequest, UsageCheckRequest


class RightsRegistryService:
    """Service layer for rights registry operations."""

    def __init__(self) -> None:
        self._rights: dict[str, dict[str, Any]] = {}
        self._licenses: dict[str, dict[str, Any]] = {}

    async def register_rights(self, request: RightsRegistrationRequest) -> dict[str, Any]:
        rights_id = f"rights-{uuid.uuid4().hex[:12]}"
        record = {
            "rights_id": rights_id,
            "asset_id": request.asset_id,
            "owner": request.owner,
            "license_type": request.license_type,
            "permitted_usage": request.permitted_usage,
            "restricted_usage": request.restricted_usage,
            "attribution_required": request.attribution_required,
            "attribution_text": request.attribution_text,
            "valid_from": request.valid_from,
            "valid_until": request.valid_until,
            "territory_restrictions": request.territory_restrictions,
            "channel_id": request.channel_id,
        }
        self._rights[rights_id] = record
        return record

    async def list_rights(self, asset_id: str | None, channel_id: str | None) -> list[dict[str, Any]]:
        items = list(self._rights.values())
        if asset_id:
            items = [r for r in items if r.get("asset_id") == asset_id]
        if channel_id:
            items = [r for r in items if r.get("channel_id") == channel_id]
        return items

    async def get_rights(self, rights_id: str) -> dict[str, Any] | None:
        return self._rights.get(rights_id)

    async def update_rights(self, rights_id: str, request: RightsUpdateRequest) -> dict[str, Any]:
        record = self._rights.get(rights_id)
        if not record:
            return {"error": "Rights record not found"}
        update_data = request.model_dump(exclude_unset=True)
        record.update(update_data)
        return record

    async def check_usage(self, rights_id: str, request: UsageCheckRequest) -> dict[str, Any]:
        record = self._rights.get(rights_id)
        if not record:
            return {"permitted": False, "reason": "Rights record not found"}
        permitted = request.usage_type in record.get("permitted_usage", [])
        return {
            "permitted": permitted,
            "conditions": ["attribution_required"] if record.get("attribution_required") else [],
            "attribution_required": record.get("attribution_required", False),
            "attribution_text": record.get("attribution_text", ""),
            "restrictions": record.get("restricted_usage", []),
        }

    async def create_license(self, request: LicenseCreateRequest) -> dict[str, Any]:
        license_id = f"license-{uuid.uuid4().hex[:12]}"
        record = {
            "license_id": license_id,
            "rights_id": request.rights_id,
            "licensee": request.licensee,
            "terms": request.terms,
            "usage_type": request.usage_type,
            "platform": request.platform,
            "territory": request.territory,
            "valid_from": request.valid_from,
            "valid_until": request.valid_until,
            "status": "active",
        }
        self._licenses[license_id] = record
        return record

    async def get_license(self, license_id: str) -> dict[str, Any] | None:
        return self._licenses.get(license_id)
