"""Data models for publications and platforms.

Pydantic models for request/response validation.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PublicationCreateRequest(BaseModel):
    """Request to create a publication."""
    channel_id: str = Field(..., min_length=1, max_length=255)
    tenant_id: str = Field(default="", max_length=255)
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="", max_length=5000)
    asset_id: str = Field(..., min_length=1)
    thumbnail_asset_id: str | None = Field(default=None)
    platforms: list[str] = Field(default_factory=list)
    scheduled_at: str | None = Field(default=None)
    seo_metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class PublicationUpdateRequest(BaseModel):
    """Request to update a publication."""
    title: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    platforms: list[str] | None = Field(default=None)
    scheduled_at: str | None = Field(default=None)
    seo_metadata: dict[str, Any] | None = Field(default=None)
    tags: list[str] | None = Field(default=None)


class ScheduleRequest(BaseModel):
    """Request to schedule a publication."""
    scheduled_at: str = Field(...)
    timezone: str = Field(default="UTC")


class Publication(BaseModel):
    """A publication record."""
    publication_id: str = Field(...)
    channel_id: str = Field(default="")
    title: str = Field(default="")
    description: str = Field(default="")
    status: str = Field(default="draft")
    asset_id: str = Field(default="")
    thumbnail_asset_id: str | None = Field(default=None)
    platforms: list[str] = Field(default_factory=list)
    scheduled_at: str | None = Field(default=None)
    seo_metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    created_at: str = Field(default="")
    updated_at: str = Field(default="")


class PlatformConfig(BaseModel):
    """A connected platform configuration."""
    platform_id: str = Field(...)
    name: str = Field(...)
    status: str = Field(default="connected")
    capabilities: list[str] = Field(default_factory=list)
    auth_status: str = Field(default="authenticated")
