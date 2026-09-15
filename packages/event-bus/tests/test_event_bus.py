"""Tests for event-bus package."""
import pytest

from event_bus.schema_validator import SchemaValidator


def test_validator_loads_schema():
    v = SchemaValidator()
    is_valid, errors = v.validate({
        "event_id": "550e8400-e29b-41d4-a716-446655440000",
        "event_type": "trend.detected",
        "timestamp": "2026-08-16T00:00:00Z",
        "channel_id": "CH-001",
        "topic_id": "TOP-001",
        "trend_signal": {
            "signal_id": "SIG-001",
            "source": "youtube_trends",
            "query": "AI agents",
            "demand_score": 0.85,
            "competition_score": 0.62,
            "freshness_score": 0.79,
            "monetization_score": 0.74,
            "risk_score": 0.18,
        }
    }, "trend_detected")
    assert is_valid, errors


def test_validator_rejects_invalid():
    v = SchemaValidator()
    is_valid, errors = v.validate({"bad": "data"}, "trend_detected")
    assert not is_valid
    assert len(errors) > 0


@pytest.mark.asyncio
async def test_connect_nats_mock_mode():
    from event_bus.client import connect_nats, NATSClientConfig, MockNATSClient

    nc = await connect_nats(NATSClientConfig(mock_mode=True))
    assert isinstance(nc, MockNATSClient)
    await nc.publish("sentra.test.event", b'{"ok":true}')
    assert len(nc.published) == 1
    assert nc.published[0][0] == "sentra.test.event"


@pytest.mark.asyncio
async def test_create_event_publisher_mock():
    from event_bus.client import create_event_publisher

    nc, pub = await create_event_publisher(mock_mode=True)
    assert nc is not None
    assert pub is not None
