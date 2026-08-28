"""Unit tests for escalation policy."""
from __future__ import annotations

import asyncio

import pytest

from notification_service.routing.escalation_policy import EscalationPolicy, EscalationRule
from notification_service.routing.severity_router import Alert, Channel, Severity


def test_handle_alert():
    policy = EscalationPolicy()
    alert = Alert(
        alert_id="e1",
        severity=Severity.ERROR,
        title="Escalation Test",
        message="msg",
        source_service="test-svc",
    )
    channels = policy.handle_alert(alert)
    assert Channel.SLACK in channels
    assert Channel.EMAIL in channels


def test_acknowledge():
    policy = EscalationPolicy()
    alert = Alert(
        alert_id="e2",
        severity=Severity.ERROR,
        title="Ack Test",
        message="msg",
        source_service="test-svc",
    )
    policy.handle_alert(alert)
    assert policy.acknowledge("e2") is True
    assert policy.acknowledge("e2") is False  # Already removed


@pytest.mark.asyncio
async def test_escalation_loop():
    policy = EscalationPolicy(
        rules=[
            EscalationRule(
                severity=Severity.ERROR,
                initial_channels=[Channel.SLACK],
                escalation_channels=[Channel.EMAIL],
                ack_timeout_seconds=1,
                max_escalations=1,
            )
        ]
    )
    dispatched = []
    policy.set_dispatch_callback(lambda alert, channels: dispatched.append((alert.alert_id, channels)))

    alert = Alert(
        alert_id="e3",
        severity=Severity.ERROR,
        title="Loop Test",
        message="msg",
        source_service="test-svc",
    )
    policy.handle_alert(alert)

    # Run one check cycle
    await policy._check_escalations()
    assert len(dispatched) == 0  # Not enough time

    await asyncio.sleep(1.5)
    await policy._check_escalations()
    assert len(dispatched) == 1
    assert dispatched[0][0] == "e3"
