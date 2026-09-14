"""Routes for the Data Ingestion Pipeline."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from data_ingestion_pipeline.pipeline import IngestionPipeline
from data_ingestion_pipeline.collectors import (
    YouTubeAnalyticsCollector,
    SocialTrendCollector,
    CompetitorCollector,
)
from data_ingestion_pipeline.normalizers import (
    YouTubeAnalyticsNormalizer,
    SocialTrendNormalizer,
    CompetitorNormalizer,
)
from data_ingestion_pipeline.config import get_settings
from data_ingestion_pipeline.publisher import NATSConfig, NATSPublisher

router = APIRouter()

settings = get_settings()
publisher = NATSPublisher(
    NATSConfig(
        servers=[settings.nats_url],
        max_connect_attempts=settings.nats_max_reconnect,
        connect_timeout_seconds=settings.nats_connect_timeout_seconds,
        reconnect_wait_seconds=settings.nats_reconnect_wait_seconds,
        mock_mode=settings.nats_mock_mode,
    )
)


@router.post("/ingest/youtube")
async def ingest_youtube(data: dict[str, Any]) -> dict[str, Any]:
    pipeline = IngestionPipeline(
        collector=YouTubeAnalyticsCollector(),
        normalizer=YouTubeAnalyticsNormalizer(),
        publisher=publisher,
    )
    job = await pipeline.run(data, subject="sentraura.events.youtube")
    return {
        "job_id": job.job_id,
        "status": job.status,
        "events_collected": job.events_collected,
        "events_normalized": job.events_normalized,
        "errors": job.errors,
    }


@router.post("/ingest/trends")
async def ingest_trends(data: dict[str, Any]) -> dict[str, Any]:
    pipeline = IngestionPipeline(
        collector=SocialTrendCollector(),
        normalizer=SocialTrendNormalizer(),
        publisher=publisher,
    )
    job = await pipeline.run(data, subject="sentraura.events.trends")
    return {
        "job_id": job.job_id,
        "status": job.status,
        "events_collected": job.events_collected,
        "events_normalized": job.events_normalized,
        "errors": job.errors,
    }


@router.post("/ingest/competitors")
async def ingest_competitors(data: dict[str, Any]) -> dict[str, Any]:
    pipeline = IngestionPipeline(
        collector=CompetitorCollector(),
        normalizer=CompetitorNormalizer(),
        publisher=publisher,
    )
    job = await pipeline.run(data, subject="sentraura.events.competitors")
    return {
        "job_id": job.job_id,
        "status": job.status,
        "events_collected": job.events_collected,
        "events_normalized": job.events_normalized,
        "errors": job.errors,
    }
