"""Regression tests for the analytics side of the publication feedback loop.

Before this suite existed, ``publication.published`` had no consumer anywhere in
the platform: the publishing service updated its own row, published nothing, and
no analytics path ever learned that content had gone live. These tests pin the
consumer, the routing state, and the truthful task-status surface.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sentinel_security import create_service_token

from analytics_ingestion import background_tasks, consumers, main, runtime
from analytics_ingestion.config import config as analytics_config
from analytics_ingestion.consumers import (
    DURABLE_NAME,
    PUBLICATION_PUBLISHED_SCHEMA,
    PUBLICATION_PUBLISHED_SUBJECT,
    PublicationTracker,
    handle_publication_published,
)

PUBLICATION_EVENT = {
    "event_id": "3f9c1a2e-0d6b-4a7f-9c1e-2b8d5f0a7c34",
    "event_type": "publication.published",
    "timestamp": "2026-09-16T10:00:00+00:00",
    "channel_id": "chan-1",
    "publication_id": "pub-1",
    "asset_id": "asset-1",
    "platform": "youtube",
    "platform_video_id": "yt-video-1",
    "published_url": "https://www.youtube.com/watch?v=yt-video-1",
}
#: ``PUBLICATION_EVENT`` carries no tenant claim, so it is filed under the
#: publisher's documented fallback rather than being dropped.
UNATTRIBUTED = PublicationTracker.UNATTRIBUTED_TENANT


def _headers(tenant_id: str | None = "tenant-aaa", **extra: str) -> dict[str, str]:
    token = create_service_token(
        "analytics-ingestion",
        ["service"],
        secret=analytics_config.jwt_secret,
        tenant_id=tenant_id,
    )
    return {"Authorization": f"Bearer {token}", **extra}


def _anonymous_client() -> TestClient:
    """A client that does NOT enter the lifespan.

    Entering the context manager starts the background scheduler and the
    feedback consumer, which changes the very runtime state the status test
    asserts on and requires a stubbed warehouse writer.
    """
    return TestClient(main.app)


def test_subject_targets_the_publisher_subject():
    """The subscription must match what EventPublisher actually emits.

    publish() builds ``sentra.<channel_id>.publication.publication_published``;
    a hard-coded channel id here would silently match nothing.
    """
    assert PUBLICATION_PUBLISHED_SUBJECT == "sentra.*.publication.publication_published"


def test_published_video_is_routed_to_its_channel():
    tracker = PublicationTracker()
    record = tracker.record(PUBLICATION_EVENT)
    assert record["publication_id"] == "pub-1"
    assert tracker.videos_for_channel("chan-1", UNATTRIBUTED) == ["yt-video-1"]
    assert tracker.videos_for_channel("other-channel", UNATTRIBUTED) == []


def test_routing_never_crosses_tenants():
    """A channel id is not unique across tenants.

    Lookups are keyed by ``(tenant, channel)``: a channel id shared between two
    tenants must not let one tenant's publication cause the fetch loop to measure
    the other tenant's videos.
    """
    tracker = PublicationTracker()
    tracker.record({**PUBLICATION_EVENT, "tenant_id": "tenant-a"})
    assert tracker.videos_for_channel("chan-1", "tenant-a") == ["yt-video-1"]
    assert tracker.videos_for_channel("chan-1", "tenant-b") == []
    assert tracker.targets() == [("tenant-a", "chan-1")]


def test_tracker_is_bounded():
    tracker = PublicationTracker(max_entries=3)
    for i in range(5):
        tracker.record({**PUBLICATION_EVENT, "publication_id": f"pub-{i}"})
    assert len(tracker.all_records()) == 3
    assert "pub-4" in {r["publication_id"] for r in tracker.all_records()}


@pytest.mark.asyncio
async def test_handler_records_publication(monkeypatch):
    monkeypatch.setattr(consumers, "tracker", PublicationTracker())
    await handle_publication_published(PUBLICATION_EVENT)
    assert consumers.tracker.videos_for_channel("chan-1", UNATTRIBUTED) == ["yt-video-1"]


def test_register_binds_schema_and_durable_name():
    class FakeConsumer:
        def __init__(self):
            self.registered = {}

        def register(self, subject, handler, *, schema_name=None, durable_name=None):
            self.registered[subject] = (handler, schema_name, durable_name)

    fake = FakeConsumer()
    consumers.register_publication_consumer(fake)
    handler, schema_name, durable_name = fake.registered[PUBLICATION_PUBLISHED_SUBJECT]
    assert handler is handle_publication_published
    assert schema_name == PUBLICATION_PUBLISHED_SCHEMA
    # A durable name must be legal for JetStream: no wildcard characters.
    assert durable_name == DURABLE_NAME
    assert "*" not in durable_name and ">" not in durable_name and "." not in durable_name


def test_published_event_satisfies_the_committed_contract():
    """The consumed payload must validate against the published JSON schema."""
    from event_bus.schema_validator import SchemaValidator

    validator = SchemaValidator()
    is_valid, errors = validator.validate(PUBLICATION_EVENT, PUBLICATION_PUBLISHED_SCHEMA)
    assert is_valid, errors


def test_envelope_missing_required_field_is_rejected():
    from event_bus.schema_validator import SchemaValidator

    validator = SchemaValidator()
    incomplete = {k: v for k, v in PUBLICATION_EVENT.items() if k != "platform"}
    is_valid, errors = validator.validate(incomplete, PUBLICATION_PUBLISHED_SCHEMA)
    assert not is_valid
    assert errors


def test_ingested_publications_endpoint_exposes_feedback(monkeypatch):
    fresh = PublicationTracker()
    monkeypatch.setattr(consumers, "tracker", fresh)
    fresh.record(PUBLICATION_EVENT)

    with TestClient(main.app) as c:
        response = c.get(
            "/api/v1/publications/ingested", headers=_headers(UNATTRIBUTED)
        )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["tenant_id"] == UNATTRIBUTED
    assert body["publications"][0]["platform_video_id"] == "yt-video-1"
    assert "consumer" in body


def test_ingested_publications_are_scoped_to_the_authenticated_tenant(monkeypatch):
    """The feedback read must not expose another tenant's publications.

    Regression: the endpoint returned every tenant's rows to any caller, and
    before auth was enforced at the boundary it served unauthenticated callers.
    """
    fresh = PublicationTracker()
    monkeypatch.setattr(consumers, "tracker", fresh)
    fresh.record({**PUBLICATION_EVENT, "tenant_id": "tenant-a"})

    with TestClient(main.app) as c:
        own = c.get("/api/v1/publications/ingested", headers=_headers("tenant-a"))
        other = c.get("/api/v1/publications/ingested", headers=_headers("tenant-b"))
        anonymous = c.get("/api/v1/publications/ingested")

    assert own.status_code == 200 and own.json()["count"] == 1
    assert other.status_code == 200 and other.json()["count"] == 0
    assert anonymous.status_code == 401


def test_task_status_reports_real_state_not_a_constant():
    """At import time the scheduler has not been started, so status must say so.

    The endpoint previously returned a hard-coded "scheduled" for every task
    regardless of whether anything was running.
    """
    # No context manager: entering one would run the application lifespan and
    # start the very scheduler whose "stopped" state is under test.
    body = _anonymous_client().get("/api/v1/tasks/status", headers=_headers()).json()
    assert body["tasks"]["video_metrics_fetch"]["status"] == "stopped"
    assert "feedback_consumer" in body
    assert body["feedback_consumer"]["subject"] == PUBLICATION_PUBLISHED_SUBJECT


def test_channel_routing_includes_configured_and_published_channels(monkeypatch):
    fresh = PublicationTracker()
    monkeypatch.setattr(consumers, "tracker", fresh)
    monkeypatch.setattr(background_tasks, "tracker", fresh)
    fresh.record(PUBLICATION_EVENT)

    configured = background_tasks.BackgroundTaskScheduler(
        youtube_client=object(),
        warehouse_writer=object(),
        channel_ids=["configured-chan"],
    )
    assert set(configured._effective_channel_ids()) == {"configured-chan", "chan-1"}
    # The published channel keeps its tenant, so the fetch loop cannot widen scope.
    assert ("system", "chan-1") in configured._effective_targets()


def test_record_endpoint_reports_real_measurement_status(monkeypatch):
    """The measurement endpoint must not launder an unconfirmed publish into success.

    Regression: the orchestrator's ``record_analytics`` activity posted to
    ``/api/v1/tasks/status``, a GET-only route, so every call returned 405 and
    nothing was ever recorded. The route it now targets distinguishes a platform
    that confirmed a video id from one that did not.
    """
    written: list[dict] = []

    class _Writer:
        async def write(self, record):
            written.append(record)

    monkeypatch.setattr(runtime, "writer", _Writer())
    fresh = PublicationTracker()
    monkeypatch.setattr(consumers, "tracker", fresh)

    c = _anonymous_client()
    confirmed = c.post(
        "/api/v1/analytics/record",
        headers=_headers("tenant-a"),
        json={
            "channel_id": "chan-1",
            "video_id": "vid-1",
            "publish_result": {
                "platform": "youtube",
                "video_id": "yt-1",
                "publication_id": "pub-1",
            },
            "clips": {"candidates": [1, 2]},
        },
    )
    unconfirmed = c.post(
        "/api/v1/analytics/record",
        headers=_headers("tenant-a"),
        json={
            "channel_id": "chan-1",
            "video_id": "vid-2",
            "publish_result": {"platform": "youtube"},
        },
    )
    anonymous = c.post("/api/v1/analytics/record", json={})

    assert confirmed.status_code == 200
    assert confirmed.json()["measurement_status"] == "recorded"
    assert confirmed.json()["tenant_id"] == "tenant-a"
    # A publish without a confirmed platform id is recorded honestly, not as success.
    assert unconfirmed.status_code == 200
    assert unconfirmed.json()["measurement_status"] == "unconfirmed"
    assert anonymous.status_code == 401
    # Only the confirmed publication becomes a fetch target for its own tenant.
    assert fresh.videos_for_channel("chan-1", "tenant-a") == ["yt-1"]
    assert len(written) == 2 and written[0]["clip_count"] == 2
