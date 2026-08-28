"""API route handlers for publishing endpoints.

Separates routing logic from main.py for testability.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from typing import Any

from publishing_service.models import PublicationCreateRequest, PublicationUpdateRequest, ScheduleRequest
from publishing_service.service import PublishingService

router = APIRouter(tags=["publications"])
service = PublishingService()


@router.post("/publications")
async def create_publication(request: PublicationCreateRequest) -> dict[str, Any]:
    """Create a publication."""
    return await service.create_publication(request)


@router.get("/publications")
async def list_publications(
    channel_id: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """List publications."""
    return await service.list_publications(channel_id, status, page, page_size)


@router.get("/publications/{publication_id}")
async def get_publication(publication_id: str) -> dict[str, Any]:
    """Get publication by ID."""
    pub = await service.get_publication(publication_id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")
    return pub


@router.put("/publications/{publication_id}")
async def update_publication(publication_id: str, request: PublicationUpdateRequest) -> dict[str, Any]:
    """Update publication."""
    return await service.update_publication(publication_id, request)


@router.delete("/publications/{publication_id}")
async def delete_publication(publication_id: str) -> None:
    """Delete/archive publication."""
    await service.delete_publication(publication_id)


@router.post("/publications/{publication_id}/publish")
async def publish_now(publication_id: str) -> dict[str, Any]:
    """Publish immediately."""
    return await service.publish_now(publication_id)


@router.post("/publications/{publication_id}/schedule")
async def schedule_publication(publication_id: str, request: ScheduleRequest) -> dict[str, Any]:
    """Schedule publication."""
    return await service.schedule_publication(publication_id, request)


@router.post("/publications/{publication_id}/unpublish")
async def unpublish(publication_id: str) -> dict[str, Any]:
    """Unpublish from platforms."""
    return await service.unpublish(publication_id)


@router.get("/platforms")
async def list_platforms() -> list[dict[str, Any]]:
    """List connected publishing platforms."""
    return await service.list_platforms()
