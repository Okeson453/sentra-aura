#!/usr/bin/env python3
# ------------------------------------------------------------------------------
# SentraAura — Seed Channels
# Populates the Content Asset Graph with initial Channel nodes for local dev.
# ------------------------------------------------------------------------------

import asyncio
import os
import sys

# Add packages to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../packages"))

from service_kit.db import get_db_session
from content_graph_service.models import Channel


SEED_CHANNELS = [
    {
        "id": "ch-001",
        "name": "SentraAura Blog",
        "slug": "sentra-blog",
        "description": "Official SentraAura product blog",
        "platform": "web",
        "status": "active",
        "config": {
            "base_url": "https://blog.sentra-aura.io",
            "rss_feed": "https://blog.sentra-aura.io/rss.xml",
        },
        "owner_id": "user-admin-001",
    },
    {
        "id": "ch-002",
        "name": "SentraAura YouTube",
        "slug": "sentra-youtube",
        "description": "Official SentraAura YouTube channel",
        "platform": "youtube",
        "status": "active",
        "config": {
            "channel_id": "UCsentraaura001",
            "api_key_ref": "secrets/youtube-api-key",
        },
        "owner_id": "user-admin-001",
    },
    {
        "id": "ch-003",
        "name": "SentraAura Podcast",
        "slug": "sentra-podcast",
        "description": "Weekly AI media operations podcast",
        "platform": "podcast",
        "status": "active",
        "config": {
            "rss_feed": "https://podcast.sentra-aura.io/feed.xml",
            "hosting_platform": "anchor",
        },
        "owner_id": "user-admin-001",
    },
    {
        "id": "ch-004",
        "name": "SentraAura LinkedIn",
        "slug": "sentra-linkedin",
        "description": "Professional updates and thought leadership",
        "platform": "linkedin",
        "status": "active",
        "config": {
            "company_page_id": "sentra-aura",
            "access_token_ref": "secrets/linkedin-token",
        },
        "owner_id": "user-admin-001",
    },
    {
        "id": "ch-005",
        "name": "SentraAura Twitter/X",
        "slug": "sentra-twitter",
        "description": "Real-time updates and community engagement",
        "platform": "twitter",
        "status": "active",
        "config": {
            "handle": "@SentraAura",
            "api_key_ref": "secrets/twitter-api-key",
        },
        "owner_id": "user-admin-001",
    },
]


async def seed_channels():
    """Insert seed channels into the database."""
    async with get_db_session() as session:
        for ch_data in SEED_CHANNELS:
            existing = await session.get(Channel, ch_data["id"])
            if existing:
                print(f"Channel {ch_data['id']} already exists, skipping")
                continue

            channel = Channel(**ch_data)
            session.add(channel)
            print(f"Created channel: {ch_data['name']} ({ch_data['id']})")

        await session.commit()
        print(f"Seeded {len(SEED_CHANNELS)} channels")


if __name__ == "__main__":
    asyncio.run(seed_channels())
