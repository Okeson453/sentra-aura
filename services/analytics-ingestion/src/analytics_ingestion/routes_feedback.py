"""Feedback-loop routes: task status, consumed publications, and recording.

The measurement leg of the operating loop lands here. The recording status is
deliberately not a blanket success: a publication whose platform id was never
confirmed is reported as ``unconfirmed`` so a platform failure cannot be
laundered into a recorded publication.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from analytics_ingestion import consumers, runtime
from analytics_ingestion.config import config
from analytics_ingestion.tenant import verify_tenant_assertion

router = APIRouter()


@router.get("/api/v1/tasks/status")
async def get_background_task_status() -> dict[str, Any]:
    """Get the real status of background ingestion and feedback tasks.

    Previously this reported every task as ``scheduled`` regardless of runtime
    state and omitted the event consumer entirely — so an operator could not
    distinguish a working loop from a completely open one. Status is read from
    the live objects.
    """
    scheduler = runtime.scheduler
    running = bool(getattr(scheduler, "_running", False))
    task_status = "running" if running else "stopped"
    return {
        "service": config.service_name,
        "tasks": {
            "video_metrics_fetch": {
                "interval_seconds": scheduler.fetch_interval,
                "status": task_status,
            },
            "warehouse_flush": {
                "interval_seconds": scheduler.flush_interval,
                "status": task_status,
            },
            "channel_health_check": {
                "interval_seconds": scheduler.health_check_interval,
                "status": task_status,
            },
        },
        "feedback_consumer": dict(runtime.consumer_state),
        "publications_tracked": len(consumers.tracker.all_records()),
        "configured_channels": len(scheduler.channel_ids),
        "writer_status": {
            "batch_size": config.batch_size,
            "flush_interval_seconds": config.flush_interval_seconds,
        },
    }


@router.get("/api/v1/publications/ingested")
async def get_ingested_publications(
    request: Request,
    channel_id: str | None = None,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Expose the publications this service has consumed for metric ingestion.

    This is the observable end of the feedback loop: a ``publication.published``
    event on the bus must appear here, and its videos must be measured by the
    periodic fetch. The response is scoped to the *authenticated* tenant — an
    earlier revision returned every tenant's rows to any caller.
    """
    acting = verify_tenant_assertion(request, tenant_id)
    records = [r for r in consumers.tracker.all_records() if r.get("tenant_id") == acting]
    if channel_id:
        records = [r for r in records if r.get("channel_id") == channel_id]
    return {
        "count": len(records),
        "tenant_id": acting,
        "consumer": dict(runtime.consumer_state),
        "publications": records,
    }


@router.post("/api/v1/analytics/record")
async def record_publication_analytics(
    request: Request,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Record the outcome of a platform publication as the first feedback datum.

    This is the endpoint the orchestrator's ``record_analytics`` activity calls.
    Before it existed that activity posted to ``/api/v1/tasks/status``, which is
    a GET-only route, so every attempt returned 405 and the loop's measurement
    step never recorded anything.
    """
    acting = verify_tenant_assertion(request, payload.get("tenant_id"))
    channel_id = payload.get("channel_id")
    video_id = payload.get("video_id")
    publish_result = payload.get("publish_result") or {}
    if not channel_id or not video_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="channel_id and video_id are required",
        )

    platform = publish_result.get("platform")
    platform_video_id = publish_result.get("video_id")
    confirmed = bool(platform_video_id) and not publish_result.get("error")

    record = {
        "tenant_id": acting,
        "channel_id": channel_id,
        "video_id": video_id,
        "platform": platform,
        "platform_video_id": platform_video_id,
        "publication_id": publish_result.get("publication_id") or payload.get("publication_id"),
        "clip_count": len((payload.get("clips") or {}).get("candidates", []) or []),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "measurement_status": "recorded" if confirmed else "unconfirmed",
    }
    # Durable path: buffered into the warehouse writer (batched insert). A
    # failure here propagates rather than reporting a false success.
    await runtime.writer.write(record)

    if confirmed:
        # A confirmed platform id is exactly the signal the fetch loop needs to
        # measure this asset on its next tick.
        consumers.tracker.record(
            {
                "tenant_id": acting,
                "channel_id": channel_id,
                "publication_id": record["publication_id"],
                "platform": platform,
                "platform_video_id": platform_video_id,
                "published_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    return {
        "event_id": f"analytics-{acting}-{channel_id}-{video_id}",
        "tenant_id": acting,
        "channel_id": channel_id,
        "video_id": video_id,
        "measurement_status": record["measurement_status"],
        "platform_video_id": platform_video_id,
        "recorded_at": record["recorded_at"],
    }
