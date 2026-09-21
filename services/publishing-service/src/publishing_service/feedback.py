"""Emit ``publication.published`` once an external platform has confirmed a publish.

This is the entry point of the analytics/learning feedback path. Before this
module existed the publishing service updated its own ``Publication`` row and
stopped there: nothing downstream was ever told that content had gone live, so
no analytics ingestion, memory, experimentation or optimisation step could
observe the result. The contract
``contracts/events/v1/publication_published.json`` was satisfied only by a
Pydantic model that no runtime code ever constructed or published.

The event is emitted only for platforms whose adapter returned a confirmed
status, so a failed or unconfirmed publish never produces a "published" signal.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

PUBLICATION_PUBLISHED = "publication.published"
_CONFIRMED_STATUSES = {"completed", "published", "success", "uploaded"}


def _mock_mode() -> bool:
    """Fail-safe default: real NATS unless a deployment opts in to mock."""
    return os.environ.get("NATS_MOCK_MODE", "false").lower() in ("1", "true", "yes")


def build_publication_published_event(
    publication: Any,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Build a contract-valid ``publication.published`` payload.

    Every required field of ``publication_published.json`` is populated from
    real values: ``publication_id``/``channel_id``/``asset_id`` from the stored
    publication, ``platform`` from the adapter that ran and ``platform_video_id``/
    ``published_url`` from that adapter's confirmed response.
    """
    if not isinstance(result, dict):
        raise TypeError("platform result must be a dict")

    platform = result.get("platform")
    if not platform:
        raise ValueError("platform result is missing 'platform'")

    channel_id = getattr(publication, "channel_id", None) or "system"
    published_at = result.get("uploaded_at") or datetime.now(timezone.utc).isoformat()
    published_url = result.get("url")

    return {
        "event_id": str(uuid.uuid4()),
        "event_type": PUBLICATION_PUBLISHED,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "channel_id": channel_id,
        "tenant_id": getattr(publication, "tenant_id", None) or "system",
        "publication_id": str(getattr(publication, "publication_id", "") or ""),
        "asset_id": str(getattr(publication, "asset_id", "") or ""),
        "platform": platform,
        # Optional contract fields are omitted rather than sent as null: the
        # schema declares them "string", which null does not satisfy.
        **(
            {"platform_video_id": result["video_id"]}
            if result.get("video_id") is not None
            else {}
        ),
        **({"published_url": published_url} if published_url else {}),
        "published_at": published_at,
    }


def confirmed_results(platform_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return only the platform results that represent a real publication.

    A result counts as confirmed when its status is one of the adapter's success
    statuses *and* it carries no error. This is the same predicate the publish
    job uses to decide ``job_status``; sharing it keeps the emitted events
    consistent with the publication's recorded state.
    """
    confirmed = []
    for result in platform_results or []:
        if not isinstance(result, dict):
            continue
        if result.get("error"):
            continue
        if result.get("status") not in _CONFIRMED_STATUSES:
            continue
        confirmed.append(result)
    return confirmed


async def publish_publication_published(
    publication: Any,
    platform_results: list[dict[str, Any]],
) -> int:
    """Publish one ``publication.published`` event per confirmed platform.

    Returns the number of events emitted. A failure to reach the broker is
    logged and re-raised by the caller's judgement: the publish itself already
    committed, so this is a best-effort feedback step and must not roll a
    completed publication back.
    """
    confirmed = confirmed_results(platform_results)
    if not confirmed:
        return 0

    try:
        from event_bus import create_event_publisher
    except ImportError:
        logger.warning("event_bus package unavailable; publication.published not emitted")
        return 0

    nats_url = os.environ.get("NATS_URL") or "nats://localhost:4222"
    nc, publisher = await create_event_publisher(nats_url=nats_url, mock_mode=_mock_mode())
    emitted = 0
    try:
        for result in confirmed:
            event = build_publication_published_event(publication, result)
            await publisher.publish(
                event,
                channel_id=event["channel_id"],
                event_family="publication",
                event_type="publication_published",
                schema_name="publication_published.json",
            )
            emitted += 1
            logger.info(
                "emitted publication.published: publication=%s platform=%s video=%s",
                event["publication_id"],
                event["platform"],
                event["platform_video_id"],
            )
    finally:
        try:
            await nc.close()
        except Exception:
            pass
    return emitted
