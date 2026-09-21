"""Process-wide singletons for the analytics ingestion service.

Kept in one module so the route modules can reference live objects (rather than
importing them at call time) and a test can substitute one without re-importing
the application.
"""
from __future__ import annotations

import logging
from typing import Any

from analytics_ingestion.background_tasks import BackgroundTaskScheduler
from analytics_ingestion.config import config
from analytics_ingestion.consumers import DURABLE_NAME, PUBLICATION_PUBLISHED_SUBJECT
from analytics_ingestion.warehouse_writer import WarehouseWriter
from analytics_ingestion.youtube_analytics_client import YouTubeAnalyticsClient

logger = logging.getLogger(__name__)

writer = WarehouseWriter(
    warehouse_url=config.warehouse_url,
    batch_size=config.batch_size,
    flush_interval_seconds=config.flush_interval_seconds,
)
yt_client = YouTubeAnalyticsClient(api_key=config.youtube_api_key)
scheduler = BackgroundTaskScheduler(
    youtube_client=yt_client,
    warehouse_writer=writer,
    channel_ids=list(config.channel_ids),
    fetch_interval_seconds=config.video_metrics_fetch_interval_seconds,
    flush_interval_seconds=config.flush_interval_seconds,
    health_check_interval_seconds=config.channel_health_check_interval_seconds,
    max_videos_per_fetch=config.max_videos_per_channel_fetch,
)

# Runtime state for the feedback consumer, reported verbatim by
# /api/v1/tasks/status so a deployment can tell "consuming feedback" apart from
# "the loop is silently open".
consumer_state: dict[str, Any] = {
    "status": "stopped",
    "subject": PUBLICATION_PUBLISHED_SUBJECT,
    "durable": DURABLE_NAME,
    "error": None,
}
nats_client: Any = None
