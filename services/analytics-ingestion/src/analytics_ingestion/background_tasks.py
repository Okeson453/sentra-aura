"""Background task scheduler for periodic analytics ingestion."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from analytics_ingestion.config import config
from analytics_ingestion.consumers import tracker
from analytics_ingestion.youtube_analytics_client import YouTubeAnalyticsClient
from analytics_ingestion.warehouse_writer import WarehouseWriter

logger = logging.getLogger(__name__)


@dataclass
class ChannelHealthRecord:
    """Health check result for a single channel."""

    channel_id: str
    checked_at: datetime
    api_reachable: bool
    quota_remaining: int | None
    error: str | None = None


class BackgroundTaskScheduler:
    """Schedules and runs periodic background tasks for analytics ingestion.

    Tasks:
    - Periodic video metrics fetch (default: every 15 minutes)
    - Periodic warehouse flush (default: every 60 seconds)
    - Periodic channel health check (default: every 5 minutes)
    """

    def __init__(
        self,
        youtube_client: YouTubeAnalyticsClient,
        warehouse_writer: WarehouseWriter,
        channel_ids: list[str] | None = None,
        fetch_interval_seconds: int = 900,
        flush_interval_seconds: int = 60,
        health_check_interval_seconds: int = 300,
        max_videos_per_fetch: int = 50,
    ) -> None:
        self.youtube_client = youtube_client
        self.warehouse_writer = warehouse_writer
        self.channel_ids = channel_ids or list(config.channel_ids)
        self.fetch_interval = fetch_interval_seconds
        self.flush_interval = flush_interval_seconds
        self.health_check_interval = health_check_interval_seconds
        self.max_videos_per_fetch = max_videos_per_fetch
        self._tasks: list[asyncio.Task] = []
        self._running = False
        self._health_records: list[ChannelHealthRecord] = []
        self._last_fetch_results: dict[str, dict[str, Any]] = {}

    async def start(self) -> None:
        """Start all background tasks."""
        self._running = True
        self._tasks = [
            asyncio.create_task(self._periodic_video_metrics_fetch(), name="video_metrics_fetch"),
            asyncio.create_task(self._periodic_warehouse_flush(), name="warehouse_flush"),
            asyncio.create_task(self._periodic_channel_health_check(), name="channel_health_check"),
        ]
        logger.info(
            "Background task scheduler started with %d tasks (channels=%d, fetch_interval=%ds, flush_interval=%ds, health_interval=%ds)",
            len(self._tasks),
            len(self.channel_ids),
            self.fetch_interval,
            self.flush_interval,
            self.health_check_interval,
        )

    async def stop(self) -> None:
        """Stop all background tasks gracefully."""
        self._running = False
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        logger.info("Background task scheduler stopped")

    async def _periodic_video_metrics_fetch(self) -> None:
        """Fetch video metrics for configured channels every N seconds."""
        while self._running:
            try:
                channels = self._effective_channel_ids()
                if channels:
                    logger.info("Starting periodic video metrics fetch for %d channels", len(channels))
                    await self._fetch_all_channels()
                else:
                    logger.debug("No channel IDs configured; skipping video metrics fetch")
                await asyncio.sleep(self.fetch_interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Video metrics fetch failed: %s", exc, exc_info=True)
                await asyncio.sleep(60)

    def _effective_channel_ids(self) -> list[str]:
        """Configured channels plus any channel that published content."""
        return sorted({channel_id for _tenant, channel_id in self._effective_targets()})

    def _effective_targets(self) -> list[tuple[str | None, str]]:
        """``(tenant_id, channel_id)`` pairs to measure on this tick.

        Configured channels are operator-supplied and therefore carry no tenant
        (``None``); channels discovered from a ``publication.published`` event
        carry the tenant that published. Keeping the tenant attached is what
        makes a *published* video measurable without widening scope: a channel
        id shared between tenants no longer causes one tenant's event to fetch
        another tenant's videos.
        """
        targets: list[tuple[str | None, str]] = [(None, c) for c in self.channel_ids]
        for tenant_id, channel_id in tracker.targets():
            pair = (tenant_id, channel_id)
            if pair not in targets:
                targets.append(pair)
        return targets

    async def _fetch_all_channels(self) -> None:
        """Fetch metrics for configured channels and for published content."""
        for tenant_id, channel_id in self._effective_targets():
            key = f"{tenant_id}:{channel_id}" if tenant_id else channel_id
            try:
                video_ids = (
                    tracker.videos_for_channel(channel_id, tenant_id)
                    if tenant_id
                    else []
                )
                measured = 0
                if video_ids:
                    video_metrics = await self.youtube_client.fetch_video_metrics(video_ids, channel_id)
                    measured = len(video_metrics)
                    for metrics in video_metrics:
                        await self.warehouse_writer.write_metrics(metrics)
                    if measured < len(video_ids):
                        # A partial response is a real signal, not a success: the
                        # platform returned fewer videos than were published.
                        logger.warning(
                            "Published-video fetch returned %d of %d video(s) for channel %s (tenant=%s)",
                            measured,
                            len(video_ids),
                            channel_id,
                            tenant_id,
                        )
                channel_metrics = await self.youtube_client.fetch_channel_metrics(channel_id)
                await self.warehouse_writer.write_metrics(channel_metrics)
                self._last_fetch_results[key] = {
                    "status": "ok",
                    "tenant_id": tenant_id,
                    "channel_id": channel_id,
                    "published_videos_expected": len(video_ids),
                    "published_videos_measured": measured,
                    "video_count": channel_metrics.video_count,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                }
                logger.info(
                    "Fetched channel metrics for %s (%d videos, %d published measured)",
                    channel_id,
                    channel_metrics.video_count,
                    measured,
                )
            except Exception as exc:
                logger.error("Failed to fetch metrics for channel %s: %s", channel_id, exc)
                self._last_fetch_results[key] = {
                    "status": "error",
                    "tenant_id": tenant_id,
                    "channel_id": channel_id,
                    "error": str(exc),
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                }

    async def _periodic_warehouse_flush(self) -> None:
        """Ensure warehouse buffer is flushed on a regular interval."""
        while self._running:
            try:
                await asyncio.sleep(self.flush_interval)
                await self.warehouse_writer.flush()
                logger.debug("Periodic warehouse flush completed")
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Warehouse flush error: %s", exc, exc_info=True)

    async def _periodic_channel_health_check(self) -> None:
        """Check channel/API health every N seconds."""
        while self._running:
            try:
                await asyncio.sleep(self.health_check_interval)
                await self._run_health_checks()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Health check failed: %s", exc, exc_info=True)

    async def _run_health_checks(self) -> None:
        """Run health checks for all configured channels."""
        logger.info("Running channel health check for %d channels", len(self.channel_ids))
        for channel_id in self.channel_ids:
            try:
                await self.youtube_client.fetch_channel_metrics(channel_id)
                quota_status = await self.youtube_client.get_quota_status()
                record = ChannelHealthRecord(
                    channel_id=channel_id,
                    checked_at=datetime.now(timezone.utc),
                    api_reachable=True,
                    quota_remaining=quota_status.remaining if quota_status else None,
                )
                self._health_records.append(record)
                logger.info("Health check OK for channel %s", channel_id)
            except Exception as exc:
                record = ChannelHealthRecord(
                    channel_id=channel_id,
                    checked_at=datetime.now(timezone.utc),
                    api_reachable=False,
                    quota_remaining=None,
                    error=str(exc),
                )
                self._health_records.append(record)
                logger.warning("Health check FAILED for channel %s: %s", channel_id, exc)

        if len(self._health_records) > 1000:
            self._health_records = self._health_records[-1000:]

    def get_health_records(
        self,
        channel_id: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[ChannelHealthRecord]:
        """Get health check records with optional filtering."""
        records = self._health_records
        if channel_id:
            records = [r for r in records if r.channel_id == channel_id]
        if since:
            records = [r for r in records if r.checked_at >= since]
        return records[-limit:]

    def get_last_fetch_results(self) -> dict[str, dict[str, Any]]:
        """Get the results of the last video metrics fetch per channel."""
        return dict(self._last_fetch_results)
