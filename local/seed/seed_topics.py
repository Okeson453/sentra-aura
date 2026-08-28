#!/usr/bin/env python3
# ------------------------------------------------------------------------------
# SentraAura — Seed Topics
# Populates the Content Asset Graph with initial Topic/Theme nodes.
# ------------------------------------------------------------------------------

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../packages"))

from service_kit.db import get_db_session
from content_graph_service.models import Topic


SEED_TOPICS = [
    {
        "id": "topic-ai-ops",
        "name": "AI Operations",
        "slug": "ai-operations",
        "description": "Operational excellence in AI-powered media systems",
        "keywords": ["ai", "operations", "automation", "orchestration"],
        "parent_id": None,
    },
    {
        "id": "topic-media-gen",
        "name": "Media Generation",
        "slug": "media-generation",
        "description": "Automated creation of video, audio, and visual content",
        "keywords": ["video", "audio", "generation", "rendering"],
        "parent_id": "topic-ai-ops",
    },
    {
        "id": "topic-content-strategy",
        "name": "Content Strategy",
        "slug": "content-strategy",
        "description": "Strategic planning and distribution of content",
        "keywords": ["strategy", "distribution", "channels", "audience"],
        "parent_id": None,
    },
    {
        "id": "topic-ml-ops",
        "name": "MLOps",
        "slug": "ml-ops",
        "description": "Machine learning operations and model lifecycle",
        "keywords": ["ml", "ops", "training", "inference", "monitoring"],
        "parent_id": "topic-ai-ops",
    },
    {
        "id": "topic-ethics",
        "name": "AI Ethics",
        "slug": "ai-ethics",
        "description": "Ethical considerations in autonomous AI media",
        "keywords": ["ethics", "bias", "fairness", "transparency"],
        "parent_id": None,
    },
    {
        "id": "topic-clipping",
        "name": "Content Clipping",
        "slug": "content-clipping",
        "description": "Automated extraction and repurposing of content segments",
        "keywords": ["clipping", "segments", "repurposing", "short-form"],
        "parent_id": "topic-media-gen",
    },
    {
        "id": "topic-analytics",
        "name": "Content Analytics",
        "slug": "content-analytics",
        "description": "Measuring and optimizing content performance",
        "keywords": ["analytics", "metrics", "optimization", "insights"],
        "parent_id": "topic-content-strategy",
    },
]


async def seed_topics():
    """Insert seed topics into the database."""
    async with get_db_session() as session:
        for topic_data in SEED_TOPICS:
            existing = await session.get(Topic, topic_data["id"])
            if existing:
                print(f"Topic {topic_data['id']} already exists, skipping")
                continue

            topic = Topic(**topic_data)
            session.add(topic)
            print(f"Created topic: {topic_data['name']} ({topic_data['id']})")

        await session.commit()
        print(f"Seeded {len(SEED_TOPICS)} topics")


if __name__ == "__main__":
    asyncio.run(seed_topics())
