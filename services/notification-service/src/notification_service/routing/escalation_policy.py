"""Escalation policy engine for unacknowledged alerts."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable

from notification_service.routing.severity_router import Alert, Channel, Severity

logger = logging.getLogger(__name__)


@dataclass
class EscalationRule:
    severity: Severity
    initial_channels: list[Channel]
    escalation_channels: list[Channel]
    ack_timeout_seconds: int
    max_escalations: int = 3


class EscalationPolicy:
    """Manages alert escalation when alerts are not acknowledged."""

    DEFAULT_RULES: list[EscalationRule] = [
        EscalationRule(
            severity=Severity.ERROR,
            initial_channels=[Channel.SLACK, Channel.EMAIL],
            escalation_channels=[Channel.PAGERDUTY],
            ack_timeout_seconds=900,  # 15 minutes
        ),
        EscalationRule(
            severity=Severity.CRITICAL,
            initial_channels=[Channel.PAGERDUTY, Channel.SLACK],
            escalation_channels=[Channel.EMAIL],
            ack_timeout_seconds=300,  # 5 minutes
        ),
    ]

    def __init__(
        self,
        rules: list[EscalationRule] | None = None,
    ) -> None:
        self.rules = {r.severity: r for r in (rules or self.DEFAULT_RULES)}
        self._pending: dict[str, dict[str, Any]] = {}  # alert_id -> {alert, rule, sent_at, escalation_count}
        self._acknowledged: set[str] = set()
        self._dispatch_callback: Callable[[Alert, list[Channel]], None] | None = None

    def set_dispatch_callback(
        self,
        callback: Callable[[Alert, list[Channel]], None],
    ) -> None:
        self._dispatch_callback = callback

    def handle_alert(self, alert: Alert) -> list[Channel]:
        """Register an alert for potential escalation."""
        rule = self.rules.get(alert.severity)
        if not rule:
            return []

        self._pending[alert.alert_id] = {
            "alert": alert,
            "rule": rule,
            "sent_at": datetime.utcnow(),
            "escalation_count": 0,
        }
        return rule.initial_channels

    def acknowledge(self, alert_id: str) -> bool:
        """Mark an alert as acknowledged, cancelling escalation."""
        if alert_id in self._pending:
            self._acknowledged.add(alert_id)
            del self._pending[alert_id]
            logger.info("Alert %s acknowledged", alert_id)
            return True
        return False

    async def run_escalation_loop(self) -> None:
        """Background task that checks for alerts needing escalation."""
        while True:
            try:
                await self._check_escalations()
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Escalation loop error: %s", exc)
                await asyncio.sleep(30)

    async def _check_escalations(self) -> None:
        now = datetime.utcnow()
        to_escalate: list[tuple[Alert, list[Channel]]] = []

        for alert_id, state in list(self._pending.items()):
            if alert_id in self._acknowledged:
                continue

            alert: Alert = state["alert"]
            rule: EscalationRule = state["rule"]
            sent_at: datetime = state["sent_at"]
            escalation_count: int = state["escalation_count"]

            if escalation_count >= rule.max_escalations:
                continue

            elapsed = (now - sent_at).total_seconds()
            if elapsed >= rule.ack_timeout_seconds * (escalation_count + 1):
                state["escalation_count"] += 1
                to_escalate.append((alert, rule.escalation_channels))
                logger.warning(
                    "Escalating alert %s to %s (escalation #%d)",
                    alert_id,
                    [c.value for c in rule.escalation_channels],
                    state["escalation_count"],
                )

        if self._dispatch_callback:
            for alert, channels in to_escalate:
                try:
                    self._dispatch_callback(alert, channels)
                except Exception as exc:
                    logger.error("Escalation dispatch failed for %s: %s", alert.alert_id, exc)
