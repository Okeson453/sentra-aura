"""Event consumers for the analytics ingestion service.

This closes the feedback half of the operating loop. A published asset emits
``publication.published``; analytics-ingestion subscribes to it, records which
video went live on which channel, and exposes those video ids so the periodic
metrics fetch measures their *real* performance. Until this existed the platform
published content that no analytics path ever observed, so no feedback reached
memory, experimentation, learning or optimisation and "closed-loop autonomy" was
not earned.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from analytics_ingestion.config import config

logger = logging.getLogger(__name__)

# ``sentra.<channel_id>.publication.publication_published`` — the '*' matches
# exactly one channel-id token.
PUBLICATION_PUBLISHED_SUBJECT = "sentra.*.publication.publication_published"
PUBLICATION_PUBLISHED_SCHEMA = "publication_published.json"
DURABLE_NAME = "analytics-publication-published"


class PublicationTracker:
    """Bounded ledger of published assets awaiting metric ingestion.

    Durability of the metrics themselves lives in the warehouse; this holds only
    the routing state that tells the fetch loop which videos to measure, so it is
    explicitly bounded rather than allowed to grow without limit.
    """

    def __init__(self, max_entries: int = 5000) -> None:
        self._max_entries = max_entries
        self._publications: dict[str, dict[str, Any]] = {}

    def record(self, event: dict[str, Any]) -> dict[str, Any]:
        """Record a publication and return the stored entry."""
        record = {
            "publication_id": event.get("publication_id"),
            "channel_id": event.get("channel_id"),
            "tenant_id": event.get("tenant_id"),
            "platform": event.get("platform"),
            "platform_video_id": event.get("platform_video_id"),
            "published_url": event.get("published_url"),
            "asset_id": event.get("asset_id"),
            "published_at": event.get("published_at")
            or datetime.now(timezone.utc).isoformat(),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        key = str(record["publication_id"] or record["platform_video_id"] or len(self._publications))
        self._publications[key] = record
        overflow = len(self._publications) - self._max_entries
        if overflow > 0:
            for stale in list(self._publications)[:overflow]:
                self._publications.pop(stale, None)
        return record

    def videos_for_channel(self, channel_id: str) -> list[str]:
        """Platform video ids observed for a channel (used by the fetch loop)."""
        return [
            str(record["platform_video_id"])
            for record in self._publications.values()
            if record.get("channel_id") == channel_id and record.get("platform_video_id")
        ]

    def all_records(self) -> list[dict[str, Any]]:
        return list(self._publications.values())

    def clear(self) -> None:
        self._publications.clear()


tracker = PublicationTracker()


async def handle_publication_published(event: dict[str, Any]) -> None:
    """Record a confirmed publication so its metrics are ingested next tick."""
    record = tracker.record(event)
    logger.info(
        "publication.published consumed: publication=%s channel=%s platform=%s video=%s",
        record["publication_id"],
        record["channel_id"],
        record["platform"],
        record["platform_video_id"],
    )


def register_publication_consumer(consumer: Any) -> None:
    """Register the publication handler on an ``EventConsumer``."""
    consumer.register(
        PUBLICATION_PUBLISHED_SUBJECT,
        handle_publication_published,
        schema_name=PUBLICATION_PUBLISHED_SCHEMA,
        durable_name=DURABLE_NAME,
    )


def _mock_mode() -> bool:
    """Fail-safe default: real NATS unless a deployment opts in to mock."""
    return os.environ.get("NATS_MOCK_MODE", "false").lower() in ("1", "true", "yes")


async def start_publication_consumer(
    nats_url: str | None = None,
    mock_mode: bool | None = None,
) -> tuple[Any, Any]:
    """Connect to NATS and start consuming ``publication.published``.

    Returns ``(nats_client, consumer)``; the caller owns closing the client on
    shutdown. Failures to connect are raised rather than swallowed, so a
    deployment cannot come up believing it consumes feedback when it does not.
    """
    from event_bus import (
        EventConsumer,
        NATSClientConfig,
        SchemaValidator,
        connect_nats,
    )

    if mock_mode is None:
        mock_mode = _mock_mode()

    cfg = NATSClientConfig(
        servers=[nats_url or config.nats_url],
        mock_mode=bool(mock_mode),
    )
    nc = await connect_nats(cfg)
    consumer = EventConsumer(nc, SchemaValidator())
    register_publication_consumer(consumer)
    await consumer.start_subscriptions()
    logger.info(
        "analytics publication consumer subscribed to %s (durable=%s)",
        PUBLICATION_PUBLISHED_SUBJECT,
        DURABLE_NAME,
    )
    return nc, consumer
