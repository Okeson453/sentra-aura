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
from data_ingestion_pipeline.publisher import NATSPublisher

router = APIRouter()

publisher = NATSPublisher()


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
