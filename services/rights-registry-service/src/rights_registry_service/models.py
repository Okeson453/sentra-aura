"""Data models for rights and licenses.

Pydantic models for request/response validation.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RightsRegistrationRequest(BaseModel):
    """Request to register usage rights."""
    asset_id: str = Field(..., min_length=1, max_length=255)
    owner: str = Field(..., min_length=1, max_length=255)
    license_type: str = Field(default="proprietary", max_length=64)
    permitted_usage: list[str] = Field(default_factory=list)
    restricted_usage: list[str] = Field(default_factory=list)
    attribution_required: bool = Field(default=False)
    attribution_text: str = Field(default="", max_length=1000)
    valid_from: str | None = Field(default=None)
    valid_until: str | None = Field(default=None)
    territory_restrictions: list[str] = Field(default_factory=list)
    channel_id: str = Field(default="", max_length=255)
    tenant_id: str = Field(default="", max_length=255)


class RightsUpdateRequest(BaseModel):
    """Request to update rights."""
    owner: str | None = Field(default=None)
    license_type: str | None = Field(default=None)
    permitted_usage: list[str] | None = Field(default=None)
    restricted_usage: list[str] | None = Field(default=None)
    attribution_required: bool | None = Field(default=None)
    valid_until: str | None = Field(default=None)
    territory_restrictions: list[str] | None = Field(default=None)


class LicenseCreateRequest(BaseModel):
    """Request to create a license."""
    rights_id: str = Field(..., min_length=1)
    licensee: str = Field(..., min_length=1)
    terms: str = Field(default="", max_length=5000)
    usage_type: str = Field(default="", max_length=255)
    platform: str = Field(default="", max_length=255)
    territory: str = Field(default="", max_length=255)
    valid_from: str | None = Field(default=None)
    valid_until: str | None = Field(default=None)


class UsageCheckRequest(BaseModel):
    """Request to check usage rights."""
    usage_type: str = Field(...)
    platform: str = Field(default="")
    territory: str = Field(default="")


class RightsRecord(BaseModel):
    """A rights record."""
    rights_id: str = Field(...)
    asset_id: str = Field(default="")
    owner: str = Field(default="")
    license_type: str = Field(default="proprietary")
    permitted_usage: list[str] = Field(default_factory=list)
    restricted_usage: list[str] = Field(default_factory=list)
    attribution_required: bool = Field(default=False)
    attribution_text: str = Field(default="")
    valid_from: str | None = Field(default=None)
    valid_until: str | None = Field(default=None)
    territory_restrictions: list[str] = Field(default_factory=list)
    channel_id: str = Field(default="")


class LicenseRecord(BaseModel):
    """A license record."""
    license_id: str = Field(...)
    rights_id: str = Field(default="")
    licensee: str = Field(default="")
    terms: str = Field(default="")
    usage_type: str = Field(default="")
    platform: str = Field(default="")
    territory: str = Field(default="")
    valid_from: str | None = Field(default=None)
    valid_until: str | None = Field(default=None)
    status: str = Field(default="active")
