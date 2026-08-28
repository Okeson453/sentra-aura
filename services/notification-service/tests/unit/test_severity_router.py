"""Unit tests for severity router."""
from __future__ import annotations

import pytest

from notification_service.routing.severity_router import Alert, Channel, Severity, SeverityRouter


def test_route_info():
    router = SeverityRouter()
    alert = Alert(
        alert_id="a1",
        severity=Severity.INFO,
        title="Test",
        message="Test message",
        source_service="test-svc",
    )
    channels = router.route(alert)
    assert Channel.SLACK in channels
    assert Channel.PAGERDUTY not in channels


def test_route_critical():
    router = SeverityRouter()
    alert = Alert(
        alert_id="a2",
        severity=Severity.CRITICAL,
        title="Critical Test",
        message="Critical message",
        source_service="test-svc",
    )
    channels = router.route(alert)
    assert Channel.PAGERDUTY in channels
    assert Channel.SLACK in channels
    assert Channel.EMAIL in channels


def test_deduplication():
    router = SeverityRouter(dedup_window_seconds=60)
    alert = Alert(
        alert_id="a3",
        severity=Severity.ERROR,
        title="Duplicate",
        message="Dup",
        source_service="test-svc",
    )
    channels1 = router.route(alert)
    assert len(channels1) > 0

    channels2 = router.route(alert)
    assert len(channels2) == 0  # Deduplicated


def test_rate_limiting():
    router = SeverityRouter(rate_limit_per_minute=2)
    for i in range(3):
        alert = Alert(
            alert_id=f"a{i}",
            severity=Severity.INFO,
            title=f"Rate {i}",
            message="msg",
            source_service="test-svc",
        )
        channels = router.route(alert)
        if i < 2:
            assert len(channels) > 0
        else:
            assert len(channels) == 0  # Rate limited
