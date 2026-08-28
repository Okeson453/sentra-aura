#!/usr/bin/env python3
# ------------------------------------------------------------------------------
# SentraAura — Seed Assets
# Populates the Content Asset Graph with initial Asset nodes for local dev.
# ------------------------------------------------------------------------------

import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../packages"))

from service_kit.db import get_db_session
from content_graph_service.models import Asset


SEED_ASSETS = [
    {
        "id": "asset-001",
        "title": "Introduction to SentraAura",
        "slug": "intro-sentra-aura",
        "asset_type": "video",
        "status": "published",
        "channel_id": "ch-001",
        "topic_ids": ["topic-ai-ops", "topic-content-strategy"],
        "metadata": {
            "duration_seconds": 300,
            "resolution": "1920x1080",
            "format": "mp4",
            "language": "en",
        },
        "content": {
            "transcript": "Welcome to SentraAura, the autonomous AI media operating system...",
            "summary": "An overview of SentraAura capabilities and architecture.",
            "tags": ["introduction", "overview", "platform"],
        },
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "published_at": datetime.now(timezone.utc),
        "owner_id": "user-admin-001",
    },
    {
        "id": "asset-002",
        "title": "Building Autonomous Agents",
        "slug": "building-autonomous-agents",
        "asset_type": "article",
        "status": "published",
        "channel_id": "ch-001",
        "topic_ids": ["topic-ai-ops", "topic-ml-ops"],
        "metadata": {
            "word_count": 2500,
            "reading_time_minutes": 12,
            "language": "en",
        },
        "content": {
            "body": "Autonomous agents are the core building blocks of modern AI systems...",
            "summary": "Deep dive into agent architecture and implementation patterns.",
            "tags": ["agents", "architecture", "autonomy"],
        },
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "published_at": datetime.now(timezone.utc),
        "owner_id": "user-admin-001",
    },
    {
        "id": "asset-003",
        "title": "Content Clipping Best Practices",
        "slug": "content-clipping-best-practices",
        "asset_type": "video",
        "status": "published",
        "channel_id": "ch-002",
        "topic_ids": ["topic-clipping", "topic-media-gen"],
        "metadata": {
            "duration_seconds": 480,
            "resolution": "1920x1080",
            "format": "mp4",
            "language": "en",
        },
        "content": {
            "transcript": "In this video we explore the best practices for automated content clipping...",
            "summary": "Learn how to optimize your clipping pipeline for maximum engagement.",
            "tags": ["clipping", "best-practices", "automation"],
        },
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "published_at": datetime.now(timezone.utc),
        "owner_id": "user-admin-001",
    },
    {
        "id": "asset-004",
        "title": "Measuring Content Performance",
        "slug": "measuring-content-performance",
        "asset_type": "podcast",
        "status": "published",
        "channel_id": "ch-003",
        "topic_ids": ["topic-analytics", "topic-content-strategy"],
        "metadata": {
            "duration_seconds": 1800,
            "format": "mp3",
            "language": "en",
        },
        "content": {
            "transcript": "Today we discuss the key metrics every content team should track...",
            "summary": "A comprehensive guide to content analytics and performance measurement.",
            "tags": ["analytics", "metrics", "performance"],
        },
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "published_at": datetime.now(timezone.utc),
        "owner_id": "user-admin-001",
    },
    {
        "id": "asset-005",
        "title": "Ethical AI in Media Production",
        "slug": "ethical-ai-media-production",
        "asset_type": "article",
        "status": "draft",
        "channel_id": "ch-001",
        "topic_ids": ["topic-ethics", "topic-ai-ops"],
        "metadata": {
            "word_count": 3200,
            "reading_time_minutes": 15,
            "language": "en",
        },
        "content": {
            "body": "As AI becomes more prevalent in media production, ethical considerations...",
            "summary": "Exploring the ethical landscape of AI-powered media creation.",
            "tags": ["ethics", "ai", "media", "responsibility"],
        },
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "published_at": None,
        "owner_id": "user-admin-001",
    },
]


async def seed_assets():
    """Insert seed assets into the database."""
    async with get_db_session() as session:
        for asset_data in SEED_ASSETS:
            existing = await session.get(Asset, asset_data["id"])
            if existing:
                print(f"Asset {asset_data['id']} already exists, skipping")
                continue

            asset = Asset(**asset_data)
            session.add(asset)
            print(f"Created asset: {asset_data['title']} ({asset_data['id']})")

        await session.commit()
        print(f"Seeded {len(SEED_ASSETS)} assets")


if __name__ == "__main__":
    asyncio.run(seed_assets())
