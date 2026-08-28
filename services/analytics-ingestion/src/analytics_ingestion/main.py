"""FastAPI application for the Analytics Ingestion Service."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.responses import JSONResponse

from analytics_ingestion.config import config
from analytics_ingestion.normalization import NormalizedMetrics, normalize_metrics, compute_performance_signal
from analytics_ingestion.warehouse_writer import WarehouseWriter
from analytics_ingestion.youtube_analytics_client import VideoMetrics, YouTubeAnalyticsClient

logger = logging.getLogger(__name__)
writer = WarehouseWriter(
    warehouse_url=config.warehouse_url,
    batch_size=config.batch_size,
    flush_interval_seconds=config.flush_interval_seconds,
)
yt_client = YouTubeAnalyticsClient(api_key=config.youtube_api_key)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await writer.start()
    logger.info("Analytics Ingestion Service started")
    yield
    await writer.stop()
    await yt_client.close()
    logger.info("Analytics Ingestion Service stopped")


app = FastAPI(
    title="Analytics Ingestion Service",
    version="1.0.0",
    description="Ingests, normalizes, and writes YouTube Analytics data to the warehouse.",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check() -> dict[str, Any]:
    return {"status": "healthy", "service": config.service_name}


@app.get("/ready")
async def readiness_check() -> dict[str, Any]:
    return {"status": "ready", "service": config.service_name}


@app.post("/api/v1/ingest/youtube")
async def ingest_youtube_metrics(
    video_ids: list[str],
    channel_id: str = Query(..., description="YouTube channel ID"),
) -> dict[str, Any]:
    """Fetch and ingest YouTube metrics for a list of videos."""
    try:
        metrics = await yt_client.fetch_video_metrics(video_ids, channel_id)
        for m in metrics:
            await writer.write_metrics(m)
        return {
            "ingested": len(metrics),
            "channel_id": channel_id,
            "video_ids": video_ids,
        }
    except Exception as exc:
        logger.error("Ingestion failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@app.post("/api/v1/normalize")
async def normalize_endpoint(
    raw_metrics: dict[str, Any],
    channel_baseline: dict[str, float],
    category_baseline: dict[str, float] | None = None,
) -> NormalizedMetrics:
    """Normalize raw metrics against baselines."""
    try:
        return normalize_metrics(raw_metrics, channel_baseline, category_baseline)
    except Exception as exc:
        logger.error("Normalization failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@app.post("/api/v1/signals")
async def compute_signals(
    metrics_history: list[dict[str, Any]],
) -> dict[str, float]:
    """Compute trend signals from a time series."""
    try:
        normalized = [
            NormalizedMetrics(**m) for m in metrics_history
        ]
        return compute_performance_signal(normalized)
    except Exception as exc:
        logger.error("Signal computation failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@app.get("/api/v1/metrics/{video_id}")
async def get_video_metrics(video_id: str) -> dict[str, Any]:
    """Retrieve cached metrics for a video (placeholder — cache layer not yet wired)."""
    return {"video_id": video_id, "status": "not_implemented_in_cache_layer", "note": "Use warehouse query endpoint for persisted metrics"}


@app.post("/api/v1/ingest/youtube/batch")
async def batch_ingest_youtube_metrics(
    channel_video_map: dict[str, list[str]],
) -> dict[str, Any]:
    """Batch ingest YouTube metrics for multiple channels.

    Args:
        channel_video_map: Dict mapping channel_id -> list of video_ids
    """
    total_ingested = 0
    channel_results = {}
    errors = []

    for channel_id, video_ids in channel_video_map.items():
        try:
            metrics = await yt_client.fetch_video_metrics(video_ids, channel_id)
            for m in metrics:
                await writer.write_metrics(m)
            total_ingested += len(metrics)
            channel_results[channel_id] = {"ingested": len(metrics), "requested": len(video_ids)}
        except Exception as exc:
            logger.error("Batch ingestion failed for channel %s: %s", channel_id, exc)
            errors.append({"channel_id": channel_id, "error": str(exc)})
            channel_results[channel_id] = {"ingested": 0, "requested": len(video_ids), "error": str(exc)}

    return {
        "total_ingested": total_ingested,
        "channels_processed": len(channel_video_map),
        "channel_results": channel_results,
        "errors": errors,
    }


@app.get("/api/v1/metrics/channel/{channel_id}")
async def get_channel_metrics(
    channel_id: str,
    include_subscribers: bool = Query(default=True),
) -> dict[str, Any]:
    """Fetch channel-level aggregate metrics from YouTube."""
    try:
        channel_metrics = await yt_client.fetch_channel_metrics(channel_id)
        result = {
            "channel_id": channel_metrics.channel_id,
            "subscriber_count": channel_metrics.subscriber_count,
            "video_count": channel_metrics.video_count,
            "view_count": channel_metrics.view_count,
            "measured_at": channel_metrics.measured_at.isoformat(),
        }
        if include_subscribers:
            result["subscriber_gain"] = channel_metrics.subscriber_count  # placeholder
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Channel metrics fetch failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@app.get("/api/v1/analytics/report")
async def get_analytics_report(
    channel_id: str = Query(...),
    start_date: str = Query(..., description="Start date YYYY-MM-DD"),
    end_date: str = Query(..., description="End date YYYY-MM-DD"),
    metrics: list[str] = Query(default=["views", "estimatedMinutesWatched", "subscribersGained"]),
) -> dict[str, Any]:
    """Request a detailed analytics report via YouTube Analytics API.

    Note: Full analytics data requires OAuth2. This endpoint returns
    the report request parameters and a placeholder result.
    """
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        report = await yt_client.fetch_analytics_report(
            channel_id=channel_id,
            video_ids=[],
            start_date=start,
            end_date=end,
            metrics=metrics,
        )
        return {
            "channel_id": channel_id,
            "start_date": start_date,
            "end_date": end_date,
            "metrics_requested": metrics,
            "report_rows": len(report),
            "data": report,
            "note": "Full analytics requires OAuth2 credentials",
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error("Analytics report failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@app.get("/api/v1/tasks/status")
async def get_background_task_status() -> dict[str, Any]:
    """Get status of background ingestion tasks."""
    return {
        "service": config.service_name,
        "tasks": {
            "video_metrics_fetch": {"interval_seconds": 900, "status": "scheduled"},
            "warehouse_flush": {"interval_seconds": 60, "status": "scheduled"},
            "channel_health_check": {"interval_seconds": 300, "status": "scheduled"},
        },
        "writer_status": {
            "batch_size": config.batch_size,
            "flush_interval_seconds": config.flush_interval_seconds,
        },
    }


@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error_code": "VALIDATION_ERROR", "message": str(exc)},
    )
