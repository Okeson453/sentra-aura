"""Unit tests for analytics normalization."""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta

from analytics_ingestion.normalization import normalize_metrics, compute_performance_signal, NormalizedMetrics


def test_normalize_basic():
    raw = {
        "video_id": "vid-123",
        "channel_id": "ch-456",
        "views": 10000,
        "ctr": 0.08,
        "average_view_duration_seconds": 240.0,
        "watch_time_seconds": 800000,
        "likes": 500,
        "comments": 100,
        "measured_at": datetime.utcnow(),
    }
    baseline = {"avg_ctr": 0.05, "avg_duration": 180.0, "avg_watch_time": 300000.0, "avg_engagement": 0.02}
    result = normalize_metrics(raw, baseline)
    assert isinstance(result, NormalizedMetrics)
    assert result.video_id == "vid-123"
    assert result.normalized_ctr > 1.0  # 0.08 > 0.05
    assert result.composite_score > 0.0
    assert 0.0 <= result.confidence <= 1.0


def test_normalize_zero_baseline():
    raw = {
        "video_id": "vid-123",
        "channel_id": "ch-456",
        "views": 100,
        "ctr": 0.0,
        "average_view_duration_seconds": 0.0,
        "watch_time_seconds": 0,
        "likes": 0,
        "comments": 0,
        "measured_at": datetime.utcnow(),
    }
    baseline = {"avg_ctr": 0.0, "avg_duration": 0.0, "avg_watch_time": 0.0, "avg_engagement": 0.0}
    result = normalize_metrics(raw, baseline)
    assert result.normalized_ctr == 0.0
    assert result.composite_score >= 0.0


def test_compute_signals():
    now = datetime.utcnow()
    history = [
        NormalizedMetrics(
            video_id="v1", channel_id="c1", views=1000,
            normalized_ctr=0.8, normalized_retention=0.7,
            normalized_engagement=0.6, normalized_watch_time=0.9,
            composite_score=0.75, confidence=0.5, measured_at=now - timedelta(days=2),
        ),
        NormalizedMetrics(
            video_id="v1", channel_id="c1", views=2000,
            normalized_ctr=0.9, normalized_retention=0.8,
            normalized_engagement=0.7, normalized_watch_time=1.0,
            composite_score=0.85, confidence=0.7, measured_at=now,
        ),
    ]
    signals = compute_performance_signal(history)
    assert "trend" in signals
    assert "volatility" in signals
    assert "momentum" in signals
    assert signals["momentum"] == pytest.approx(0.10, abs=0.01)


def test_compute_signals_insufficient():
    signals = compute_performance_signal([])
    assert signals["trend"] == 0.0
    assert signals["momentum"] == 0.0


def test_normalize_accepts_iso_string_measured_at():
    """measured_at arrives as a JSON string over the REST surface, not a datetime."""
    raw = {
        "video_id": "v1",
        "channel_id": "c1",
        "views": 5000,
        "ctr": 0.06,
        "average_view_duration_seconds": 200.0,
        "watch_time_seconds": 400000,
        "likes": 300,
        "comments": 50,
        "measured_at": "2024-01-15T12:00:00",
    }
    baseline = {"avg_ctr": 0.05, "avg_duration": 180.0, "avg_watch_time": 300000.0, "avg_engagement": 0.02}
    result = normalize_metrics(raw, baseline)
    assert isinstance(result, NormalizedMetrics)
    assert result.measured_at == datetime(2024, 1, 15, 12, 0, 0)
    assert result.composite_score > 0.0


def test_normalize_accepts_z_suffixed_measured_at():
    """Z-suffixed / timezone-aware timestamps must not raise, and stay naive UTC."""
    result = normalize_metrics(
        {"video_id": "v1", "channel_id": "c1", "views": 5000, "measured_at": "2024-01-15T12:00:00Z"},
        {},
    )
    assert result.measured_at == datetime(2024, 1, 15, 12, 0, 0)
    assert result.measured_at.tzinfo is None


def test_normalize_handles_missing_and_unparseable_measured_at():
    missing = normalize_metrics({"video_id": "v1", "channel_id": "c1", "views": 10}, {})
    assert isinstance(missing.measured_at, datetime)
    unparseable = normalize_metrics(
        {"video_id": "v1", "channel_id": "c1", "views": 10, "measured_at": "not-a-date"}, {}
    )
    assert isinstance(unparseable.measured_at, datetime)
