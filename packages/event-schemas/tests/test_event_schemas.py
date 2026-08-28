"""Tests for event-schemas package."""
import pytest
from datetime import datetime

from event_schemas.registry_client import SchemaRegistryClient
from event_schemas.v1 import TrendDetected, TrendSignal


def test_registry_lists_schemas():
    client = SchemaRegistryClient()
    schemas = client.list_schemas()
    assert "trend_detected" in schemas
    assert "script_drafted" in schemas


def test_registry_validates_event():
    client = SchemaRegistryClient()
    event = TrendDetected(
        event_id="550e8400-e29b-41d4-a716-446655440000",
        timestamp=datetime.utcnow(),
        channel_id="CH-001",
        topic_id="TOP-001",
        trend_signal=TrendSignal(
            signal_id="SIG-001",
            source="youtube_trends",
            query="AI agents",
            demand_score=0.85,
            competition_score=0.62,
            freshness_score=0.79,
            monetization_score=0.74,
            risk_score=0.18,
        ),
    )
    is_valid, errors = client.validate(event.model_dump(mode="json", exclude_none=True), "trend_detected")
    assert is_valid, errors


def test_trend_detected_model():
    ts = TrendSignal(
        signal_id="SIG-001",
        source="youtube_trends",
        query="test",
        demand_score=0.5,
        competition_score=0.5,
        freshness_score=0.5,
        monetization_score=0.5,
        risk_score=0.5,
    )
    assert ts.demand_score == 0.5
