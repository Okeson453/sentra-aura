"""Metric ingestion and normalization routes.

Every mutating route resolves the acting tenant from the verified
authentication context (see ``analytics_ingestion.tenant``), so a caller cannot
choose whose data it touches.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status

from analytics_ingestion import runtime
from analytics_ingestion.normalization import (
    NormalizedMetrics,
    compute_performance_signal,
    normalize_metrics,
)
from analytics_ingestion.tenant import verify_tenant_assertion

router = APIRouter()


@router.post("/api/v1/ingest/youtube")
async def ingest_youtube_metrics(
    request: Request,
    video_ids: list[str],
    channel_id: str = Query(..., description="YouTube channel ID"),
    tenant_id: str | None = Query(default=None, description="Asserted tenant; must match the token"),
) -> dict[str, Any]:
    """Fetch and ingest YouTube metrics for a list of videos."""
    acting = verify_tenant_assertion(request, tenant_id)
    try:
        metrics = await runtime.yt_client.fetch_video_metrics(video_ids, channel_id)
        for m in metrics:
            await runtime.writer.write_metrics(m)
        await runtime.writer.flush()
        return {
            "ingested": len(metrics),
            "channel_id": channel_id,
            "tenant_id": acting,
            "video_ids": video_ids,
        }
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.post("/api/v1/ingest/youtube/batch")
async def batch_ingest_youtube_metrics(
    request: Request,
    channel_video_map: dict[str, list[str]],
    tenant_id: str | None = Query(default=None, description="Asserted tenant; must match the token"),
) -> dict[str, Any]:
    """Batch ingest YouTube metrics for multiple channels.

    Args:
        channel_video_map: Dict mapping channel_id -> list of video_ids
    """
    acting = verify_tenant_assertion(request, tenant_id)
    total_ingested = 0
    channel_results: dict[str, Any] = {}
    errors: list[dict[str, Any]] = []

    for channel_id, video_ids in channel_video_map.items():
        try:
            metrics = await runtime.yt_client.fetch_video_metrics(video_ids, channel_id)
            for m in metrics:
                await runtime.writer.write_metrics(m)
            await runtime.writer.flush()
            total_ingested += len(metrics)
            channel_results[channel_id] = {"ingested": len(metrics), "requested": len(video_ids)}
        except Exception as exc:
            errors.append({"channel_id": channel_id, "error": str(exc)})
            channel_results[channel_id] = {
                "ingested": 0,
                "requested": len(video_ids),
                "error": str(exc),
            }

    return {
        "total_ingested": total_ingested,
        "tenant_id": acting,
        "channels_processed": len(channel_video_map),
        "channel_results": channel_results,
        "errors": errors,
    }


@router.post("/api/v1/normalize")
async def normalize_endpoint(
    request: Request,
    raw_metrics: dict[str, Any],
    channel_baseline: dict[str, float],
    category_baseline: dict[str, float] | None = None,
) -> NormalizedMetrics:
    """Normalize raw metrics against baselines."""
    verify_tenant_assertion(request, raw_metrics.get("tenant_id"))
    try:
        return normalize_metrics(raw_metrics, channel_baseline, category_baseline)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/api/v1/signals")
async def compute_signals(
    request: Request,
    metrics_history: list[dict[str, Any]],
) -> dict[str, float]:
    """Compute trend signals from a time series.

    The caller must send ``NormalizedMetrics`` records. Until the feedback loop
    was audited the orchestrator sent a raw activity result here, which this
    handler rejected as a 400 — so a *successful* activity was in fact a failed
    call, and the learning leg of the loop never produced a signal.
    """
    for entry in metrics_history:
        if isinstance(entry, dict):
            verify_tenant_assertion(request, entry.get("tenant_id"))
    try:
        normalized = [NormalizedMetrics(**m) for m in metrics_history]
        return compute_performance_signal(normalized)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/api/v1/metrics/{video_id}")
async def get_video_metrics(video_id: str) -> dict[str, Any]:
    """Retrieve cached metrics for a video (cache layer not yet wired)."""
    return {
        "video_id": video_id,
        "status": "not_implemented_in_cache_layer",
        "note": "Use warehouse query endpoint for persisted metrics",
    }


@router.get("/api/v1/metrics/channel/{channel_id}")
async def get_channel_metrics(
    channel_id: str,
    include_subscribers: bool = Query(default=True),
) -> dict[str, Any]:
    """Fetch channel-level aggregate metrics from YouTube."""
    try:
        channel_metrics = await runtime.yt_client.fetch_channel_metrics(channel_id)
        result = {
            "channel_id": channel_metrics.channel_id,
            "subscriber_count": channel_metrics.subscriber_count,
            "video_count": channel_metrics.video_count,
            "view_count": channel_metrics.view_count,
            "measured_at": channel_metrics.measured_at.isoformat(),
        }
        if include_subscribers:
            result["subscriber_gain"] = channel_metrics.subscriber_count
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.get("/api/v1/analytics/report")
async def get_analytics_report(
    channel_id: str = Query(...),
    start_date: str = Query(..., description="Start date YYYY-MM-DD"),
    end_date: str = Query(..., description="End date YYYY-MM-DD"),
    metrics: list[str] = Query(default=["views", "estimatedMinutesWatched", "subscribersGained"]),
) -> dict[str, Any]:
    """Request a detailed analytics report via the YouTube Analytics API.

    Full analytics data requires OAuth2; the rows are whatever the configured
    client actually returned, and ``report_rows`` reflects that count rather
    than a placeholder success.
    """
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        report = await runtime.yt_client.fetch_analytics_report(
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
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
