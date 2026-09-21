"""Regression tests for the analytics side of the publication feedback loop.

Before this suite existed, ``publication.published`` had no consumer anywhere in
the platform: the publishing service updated its own row, published nothing, and
no analytics path ever learned that content had gone live. These tests pin the
consumer, the routing state, and the truthful task-status surface.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from analytics_ingestion import background_tasks, consumers, main
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
    assert tracker.videos_for_channel("chan-1") == ["yt-video-1"]
    assert tracker.videos_for_channel("other-channel") == []


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
    assert consumers.tracker.videos_for_channel("chan-1") == ["yt-video-1"]


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
    monkeypatch.setattr(consumers, "tracker", PublicationTracker())
    monkeypatch.setattr(main, "tracker", consumers.tracker)
    consumers.tracker.record(PUBLICATION_EVENT)

    response = TestClient(main.app).get("/api/v1/publications/ingested")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["publications"][0]["platform_video_id"] == "yt-video-1"
    assert "consumer" in body


def test_task_status_reports_real_state_not_a_constant():
    """At import time the scheduler has not been started, so status must say so.

    The endpoint previously returned a hard-coded "scheduled" for every task
    regardless of whether anything was running.
    """
    body = TestClient(main.app).get("/api/v1/tasks/status").json()
    assert body["tasks"]["video_metrics_fetch"]["status"] == "stopped"
    assert "feedback_consumer" in body
    assert body["feedback_consumer"]["subject"] == PUBLICATION_PUBLISHED_SUBJECT


def test_channel_routing_includes_configured_and_published_channels(monkeypatch):
    fresh = PublicationTracker()
    # ``background_tasks`` binds ``tracker`` at import time, so patching only the
    # consumers/main names would leave the scheduler reading the original object.
    monkeypatch.setattr(consumers, "tracker", fresh)
    monkeypatch.setattr(main, "tracker", fresh)
    monkeypatch.setattr(background_tasks, "tracker", fresh)
    fresh.record(PUBLICATION_EVENT)

    configured = main.BackgroundTaskScheduler(
        youtube_client=object(),
        warehouse_writer=object(),
        channel_ids=["configured-chan"],
    )
    assert set(configured._effective_channel_ids()) == {"configured-chan", "chan-1"}
