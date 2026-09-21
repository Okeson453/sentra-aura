"""Regression tests for the publication.published feedback emitter.

The publishing service previously completed a publish and told nobody. These
tests pin the contract shape and, critically, that a *failed* platform result
can never produce a "published" signal.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from publishing_service.feedback import (
    build_publication_published_event,
    confirmed_results,
    publish_publication_published,
)

SCHEMA = "publication_published.json"


@dataclass
class FakePublication:
    publication_id: str = "pub-1"
    channel_id: str = "chan-1"
    asset_id: str = "asset-1"
    tenant_id: str = "tenant-1"


CONFIRMED = {
    "platform": "youtube",
    "video_id": "yt-video-1",
    "status": "uploaded",
    "url": "https://www.youtube.com/watch?v=yt-video-1",
    "uploaded_at": "2026-09-16T10:00:00Z",
}
FAILED = {"platform": "youtube", "status": "failed", "error": "quota exhausted"}
UNCONFIRMED = {"platform": "youtube", "status": "pending", "video_id": "yt-x"}


def test_build_is_contract_valid():
    from event_bus.schema_validator import SchemaValidator

    event = build_publication_published_event(FakePublication(), CONFIRMED)
    assert event["event_type"] == "publication.published"
    is_valid, errors = SchemaValidator().validate(event, SCHEMA)
    assert is_valid, errors


def test_build_routes_real_adapter_values():
    event = build_publication_published_event(FakePublication(), CONFIRMED)
    assert event["platform"] == "youtube"
    assert event["platform_video_id"] == "yt-video-1"
    assert event["published_url"].endswith("yt-video-1")
    assert event["publication_id"] == "pub-1"
    assert event["channel_id"] == "chan-1"
    assert event["asset_id"] == "asset-1"


def test_build_falls_back_to_system_when_channel_absent():
    event = build_publication_published_event(FakePublication(channel_id=""), CONFIRMED)
    assert event["channel_id"] == "system"


def test_build_without_platform_is_rejected():
    with pytest.raises(ValueError):
        build_publication_published_event(FakePublication(), {"video_id": "x"})


def test_failed_result_is_not_confirmed():
    assert confirmed_results([FAILED]) == []


def test_pending_result_is_not_confirmed():
    assert confirmed_results([UNCONFIRMED]) == []


def test_confirmed_result_requires_status_and_absence_of_error():
    assert confirmed_results([CONFIRMED]) == [CONFIRMED]
    # A success status carrying an error is still a failure.
    assert confirmed_results([{**CONFIRMED, "error": "thumbnail failed"}]) == []


@pytest.mark.asyncio
async def test_no_event_is_emitted_for_a_failed_publish():
    """The critical guarantee: a failed publish must not announce success."""
    emitted = await publish_publication_published(FakePublication(), [FAILED, UNCONFIRMED])
    assert emitted == 0


@pytest.mark.asyncio
async def test_no_event_is_emitted_when_there_are_no_results():
    assert await publish_publication_published(FakePublication(), []) == 0


@pytest.mark.asyncio
async def test_mock_mode_emits_one_event_per_confirmed_platform(monkeypatch):
    monkeypatch.setenv("NATS_MOCK_MODE", "true")
    emitted = await publish_publication_published(
        FakePublication(),
        [CONFIRMED, {**CONFIRMED, "platform": "tiktok", "video_id": "tt-1"}],
    )
    assert emitted == 2
