"""Background tasks for analytics ingestion (scheduled metric fetching)."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from analytics_ingestion.config import config
from analytics_ingestion.consumers import tracker
from analytics_ingestion.warehouse_writer import WarehouseWriter
from analytics_ingestion.youtube_analytics_client import YouTubeAnalyticsClient

logger = logging.getLogger(__name__)


class BackgroundTaskScheduler:
    """Schedules periodic metric fetching and channel-health checks."""

    def __init__(self) -> None:
        self.youtube_client = YouTubeAnalyticsClient()
        self.warehouse_writer = WarehouseWriter()
        self._tasks: list[asyncio.Task] = []
        self._running = False
        self._last_fetch_results: dict[str, Any] = {}

    @property
    def channel_ids(self) -> list[str]:
        return list(config.channel_ids)

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

    async def _fetch_loop(self) -> None:
        """Fetch metrics on a fixed interval until cancelled."""
        while self._running:
            await self._fetch_all_channels()
            await asyncio.sleep(config.video_metrics_fetch_interval_seconds)

    async def _health_loop(self) -> None:
        """Periodic channel health check until cancelled."""
        while self._running:
            await asyncio.sleep(config.channel_health_check_interval_seconds)
            for tenant_id, channel_id in self._effective_targets():
                try:
                    await self.youtube_client.fetch_channel_metrics(channel_id)
                except Exception as exc:
                    logger.warning("Channel health check failed for %s: %s", channel_id, exc)

    async def start(self) -> None:
        """Start the scheduled background loops."""
        if self._running:
            return
        self._running = True
        self._tasks = [
            asyncio.create_task(self._fetch_loop()),
            asyncio.create_task(self._health_loop()),
        ]
        logger.info(
            "Background ingestion started (fetch every %ds)",
            config.video_metrics_fetch_interval_seconds,
        )

    async def stop(self) -> None:
        """Stop the loops and await their cancellation."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks = []
        logger.info("Background ingestion stopped")

    def status(self) -> dict[str, Any]:
        """Report REAL task state, not a constant.

        An earlier revision returned a hard-coded "scheduled" for every task
        even when nothing had been started, which is a false observability
        signal rather than a health report.
        """
        state = "running" if self._running else "stopped"
        return {
            "video_metrics_fetch": {
                "status": state,
                "interval_seconds": config.video_metrics_fetch_interval_seconds,
            },
            "channel_health_check": {
                "status": state,
                "interval_seconds": config.channel_health_check_interval_seconds,
            },
            "last_fetch_results": self._last_fetch_results,
        }


scheduler = BackgroundTaskScheduler()
