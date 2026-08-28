"""Client for the Data Ingestion Pipeline (Architecture §51.1).

This agent is the sole consumer of data-ingestion-pipeline for trend/social/
competitor signals. Uses the typed package client under packages/api-clients.
"""
from __future__ import annotations

import logging
from typing import Any

from api_clients.data_ingestion_pipeline import DataIngestionPipelineClient

logger = logging.getLogger(__name__)


class MarketDataIngestionClient:
    """Agent-facing wrapper around DataIngestionPipelineClient."""

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self._client = DataIngestionPipelineClient(base_url=base_url, timeout=timeout)

    async def close(self) -> None:
        await self._client.close()

    async def fetch_trends(
        self,
        *,
        market_segment: str,
        geo: str = "US",
        time_window_days: int = 30,
        channels_of_interest: list[str] | None = None,
    ) -> dict[str, Any]:
        """Trigger trend ingestion and return job + any signals in the response.

        Tool name registered in tool_permissions: fetch_trends.
        """
        payload: dict[str, Any] = {
            "topic": market_segment,
            "geo": geo,
            "time_window_days": time_window_days,
        }
        if channels_of_interest:
            payload["channels"] = channels_of_interest
        logger.info("fetch_trends → data-ingestion-pipeline /ingest/trends segment=%s", market_segment)
        result = await self._client.ingest_trends(payload)
        return result

    async def fetch_youtube_signals(
        self,
        *,
        channel_id: str | None = None,
        market_segment: str = "general",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"topic": market_segment}
        if channel_id:
            payload["channel_id"] = channel_id
        logger.info("fetch_youtube → data-ingestion-pipeline /ingest/youtube")
        return await self._client.ingest_youtube(payload)

    async def fetch_competitors(
        self,
        *,
        competitor_channels: list[str],
        market_segment: str = "general",
    ) -> list[dict[str, Any]]:
        """Ingest competitor data for each competitor channel id/handle."""
        jobs: list[dict[str, Any]] = []
        for competitor_id in competitor_channels:
            payload = {
                "competitor_id": competitor_id,
                "topic": market_segment,
            }
            logger.info("fetch_competitors → /ingest/competitors id=%s", competitor_id)
            jobs.append(await self._client.ingest_competitors(payload))
        return jobs
