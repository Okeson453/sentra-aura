"""Event normalizers for SentraAura."""
from __future__ import annotations

from typing import Any

from data_ingestion_pipeline.models import RawEvent, NormalizedEvent


class BaseNormalizer:
    """Base class for event normalizers."""

    def __init__(self, source: str) -> None:
        self.source = source

    async def normalize(self, event: RawEvent) -> NormalizedEvent:
        raise NotImplementedError


class YouTubeAnalyticsNormalizer(BaseNormalizer):
    """Normalizer for YouTube analytics events."""

    def __init__(self) -> None:
        super().__init__("youtube_analytics")

    async def normalize(self, event: RawEvent) -> NormalizedEvent:
        payload = event.raw_payload
        return NormalizedEvent(
            event_id=event.event_id,
            source=self.source,
            event_type="performance_metrics",
            channel_id=event.channel_id,
            tenant_id=event.tenant_id,
            payload={
                "views": payload.get("views", 0),
                "watch_time_seconds": payload.get("watch_time", 0),
            },
            metadata={"collected_at": event.collected_at.isoformat()},
        )


class SocialTrendNormalizer(BaseNormalizer):
    """Normalizer for social trend events."""

    def __init__(self) -> None:
        super().__init__("social_trends")

    async def normalize(self, event: RawEvent) -> NormalizedEvent:
        payload = event.raw_payload
        return NormalizedEvent(
            event_id=event.event_id,
            source=self.source,
            event_type="trend_signal",
            channel_id=event.channel_id,
            tenant_id=event.tenant_id,
            payload={
                "topic": payload.get("topic", ""),
                "trend_score": payload.get("trend_score", 0.0),
                "volume": payload.get("volume", 0),
            },
        )


class CompetitorNormalizer(BaseNormalizer):
    """Normalizer for competitor events."""

    def __init__(self) -> None:
        super().__init__("competitor_data")

    async def normalize(self, event: RawEvent) -> NormalizedEvent:
        payload = event.raw_payload
        return NormalizedEvent(
            event_id=event.event_id,
            source=self.source,
            event_type="competitor_activity",
            channel_id=event.channel_id,
            tenant_id=event.tenant_id,
            payload={
                "competitor_id": payload.get("competitor_id", ""),
                "latest_video_views": payload.get("latest_video_views", 0),
            },
        )


# Convenience function wrappers for test compatibility
async def normalize_youtube_analytics(event: RawEvent) -> NormalizedEvent:
    return await YouTubeAnalyticsNormalizer().normalize(event)


async def normalize_social_trends(event: RawEvent) -> NormalizedEvent:
    return await SocialTrendNormalizer().normalize(event)


async def normalize_competitor_data(event: RawEvent) -> NormalizedEvent:
    return await CompetitorNormalizer().normalize(event)


async def normalize_rss_feed(event: RawEvent) -> NormalizedEvent:
    """Normalize RSS feed events."""
    payload = event.raw_payload
    return NormalizedEvent(
        event_id=event.event_id,
        source="rss_feed",
        event_type="rss_item",
        channel_id=event.channel_id,
        tenant_id=event.tenant_id,
        payload={
            "title": payload.get("title", ""),
            "url": payload.get("url", ""),
            "published_at": payload.get("published_at", ""),
        },
    )
