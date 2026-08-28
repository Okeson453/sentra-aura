"""Business logic for publishing and platform management.

Encapsulates all domain operations behind a service layer.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from publishing_service.models import PublicationCreateRequest, PublicationUpdateRequest, ScheduleRequest


class PublishingService:
    """Service layer for publishing operations."""

    def __init__(self) -> None:
        self._publications: dict[str, dict[str, Any]] = {}
        self._platforms: list[dict[str, Any]] = [
            {"platform_id": "youtube", "name": "YouTube", "status": "connected", "capabilities": ["upload", "schedule", "analytics"]},
            {"platform_id": "tiktok", "name": "TikTok", "status": "connected", "capabilities": ["upload", "schedule"]},
            {"platform_id": "instagram", "name": "Instagram", "status": "connected", "capabilities": ["upload", "schedule"]},
            {"platform_id": "twitter", "name": "X / Twitter", "status": "connected", "capabilities": ["upload"]},
        ]

    async def create_publication(self, request: PublicationCreateRequest) -> dict[str, Any]:
        publication_id = f"pub-{uuid.uuid4().hex[:12]}"
        pub = {
            "publication_id": publication_id,
            "channel_id": request.channel_id,
            "title": request.title,
            "description": request.description,
            "status": "draft",
            "asset_id": request.asset_id,
            "thumbnail_asset_id": request.thumbnail_asset_id,
            "platforms": request.platforms,
            "scheduled_at": request.scheduled_at,
            "seo_metadata": request.seo_metadata,
            "tags": request.tags,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        self._publications[publication_id] = pub
        return pub

    async def list_publications(self, channel_id: str | None, status: str | None, page: int, page_size: int) -> dict[str, Any]:
        items = list(self._publications.values())
        if channel_id:
            items = [p for p in items if p.get("channel_id") == channel_id]
        if status:
            items = [p for p in items if p.get("status") == status]
        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        return {
            "items": items[start:end],
            "pagination": {"page": page, "page_size": page_size, "total": total, "total_pages": (total + page_size - 1) // page_size},
        }

    async def get_publication(self, publication_id: str) -> dict[str, Any] | None:
        return self._publications.get(publication_id)

    async def update_publication(self, publication_id: str, request: PublicationUpdateRequest) -> dict[str, Any]:
        pub = self._publications.get(publication_id)
        if not pub:
            return {"error": "Publication not found"}
        update_data = request.model_dump(exclude_unset=True)
        pub.update(update_data)
        pub["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return pub

    async def delete_publication(self, publication_id: str) -> None:
        if publication_id in self._publications:
            self._publications[publication_id]["status"] = "archived"

    async def publish_now(self, publication_id: str) -> dict[str, Any]:
        pub = self._publications.get(publication_id)
        if not pub:
            return {"error": "Publication not found"}
        job_id = f"publish-{uuid.uuid4().hex[:12]}"
        return {"job_id": job_id, "publication_id": publication_id, "status": "queued", "platform_results": []}

    async def schedule_publication(self, publication_id: str, request: ScheduleRequest) -> dict[str, Any]:
        pub = self._publications.get(publication_id)
        if not pub:
            return {"error": "Publication not found"}
        pub["scheduled_at"] = request.scheduled_at
        pub["status"] = "scheduled"
        return pub

    async def unpublish(self, publication_id: str) -> dict[str, Any]:
        pub = self._publications.get(publication_id)
        if not pub:
            return {"error": "Publication not found"}
        pub["status"] = "archived"
        return {"status": "unpublished", "publication_id": publication_id}

    async def list_platforms(self) -> list[dict[str, Any]]:
        return self._platforms
