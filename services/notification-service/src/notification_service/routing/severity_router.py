"""Severity-to-channel routing with deduplication, rate limiting, and circuit breaker patterns."""
from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class Severity(str, Enum):
    """Alert severity levels aligned with operational response requirements."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Channel(str, Enum):
    """Available notification channels."""

    SLACK = "slack"
    EMAIL = "email"
    PAGERDUTY = "pagerduty"
    SMS = "sms"
    WEBHOOK = "webhook"
    NONE = "none"


@dataclass(frozen=True)
class Alert:
    """Standardized alert payload for the notification service."""

    alert_id: str
    severity: Severity
    title: str
    message: str
    source_service: str
    channel_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    correlation_id: str | None = None
    runbook_url: str | None = None

    def fingerprint(self) -> str:
        """Generate a deterministic deduplication key.

        The fingerprint combines source service, alert title, and severity
        to identify duplicate alerts within the deduplication window.
        """
        base = f"{self.source_service}:{self.title}:{self.severity.value}"
        if self.correlation_id:
            base += f":{self.correlation_id}"
        return hashlib.sha256(base.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "source_service": self.source_service,
            "channel_id": self.channel_id,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
            "runbook_url": self.runbook_url,
        }


class CircuitBreaker:
    """Circuit breaker pattern for notification channels.

    Prevents notification storms by temporarily disabling channels
    that are experiencing high failure rates.
    """

    STATE_CLOSED = "closed"      # Normal operation
    STATE_OPEN = "open"          # Failing, reject requests
    STATE_HALF_OPEN = "half_open"  # Testing if recovered

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self._state = self.STATE_CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float | None = None
        self._half_open_calls = 0

    @property
    def state(self) -> str:
        if self._state == self.STATE_OPEN:
            if self._last_failure_time and (time.time() - self._last_failure_time) >= self.recovery_timeout:
                self._state = self.STATE_HALF_OPEN
                self._half_open_calls = 0
                logger.info("Circuit breaker entering half-open state")
        return self._state

    def record_success(self) -> None:
        if self._state == self.STATE_HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.half_open_max_calls:
                self._state = self.STATE_CLOSED
                self._failure_count = 0
                self._success_count = 0
                logger.info("Circuit breaker closed after successful recovery")
        else:
            self._failure_count = 0

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._state == self.STATE_HALF_OPEN:
            self._state = self.STATE_OPEN
            logger.warning("Circuit breaker opened again after half-open failure")
        elif self._failure_count >= self.failure_threshold:
            self._state = self.STATE_OPEN
            logger.warning("Circuit breaker opened after %d failures", self.failure_count)

    def can_execute(self) -> bool:
        state = self.state
        if state == self.STATE_CLOSED:
            return True
        if state == self.STATE_HALF_OPEN:
            if self._half_open_calls < self.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False
        return False


class SeverityRouter:
    """Routes alerts to channels based on severity, policy, and channel health.

    Features:
    - Severity-based channel mapping (configurable)
    - Alert deduplication within configurable time windows
    - Per-channel rate limiting
    - Circuit breaker pattern for failing channels
    - Dynamic routing table overrides
    """

    DEFAULT_ROUTING: dict[Severity, list[Channel]] = {
        Severity.INFO: [Channel.SLACK],
        Severity.WARNING: [Channel.SLACK, Channel.EMAIL],
        Severity.ERROR: [Channel.SLACK, Channel.EMAIL, Channel.PAGERDUTY],
        Severity.CRITICAL: [Channel.PAGERDUTY, Channel.SLACK, Channel.EMAIL],
    }

    def __init__(
        self,
        routing_table: dict[Severity, list[Channel]] | None = None,
        dedup_window_seconds: int = 300,
        rate_limit_per_minute: int = 100,
        enable_circuit_breaker: bool = True,
    ) -> None:
        self.routing_table = routing_table or dict(self.DEFAULT_ROUTING)
        self.dedup_window = dedup_window_seconds
        self.rate_limit = rate_limit_per_minute
        self.enable_circuit_breaker = enable_circuit_breaker

        # Deduplication state: fingerprint -> last_sent_timestamp
        self._recent: dict[str, float] = {}

        # Rate limiting state
        self._minute_count: int = 0
        self._minute_start: float = time.time()

        # Circuit breakers per channel
        self._circuit_breakers: dict[Channel, CircuitBreaker] = {}
        if enable_circuit_breaker:
            for channel in Channel:
                if channel != Channel.NONE:
                    self._circuit_breakers[channel] = CircuitBreaker()

    def route(self, alert: Alert) -> list[Channel]:
        """Determine which channels should receive this alert.

        Applies the following filters in order:
        1. Rate limiting (global)
        2. Deduplication
        3. Circuit breaker status
        4. Severity-based routing table
        """
        now = time.time()

        # 1. Global rate limiting
        if now - self._minute_start >= 60:
            self._minute_count = 0
            self._minute_start = now
        self._minute_count += 1
        if self._minute_count > self.rate_limit:
            logger.warning(
                "Global rate limit exceeded (%d/min); dropping alert %s",
                self.rate_limit,
                alert.alert_id,
            )
            return []

        # 2. Deduplication
        fp = alert.fingerprint()
        last_sent = self._recent.get(fp, 0)
        if now - last_sent < self.dedup_window:
            logger.info(
                "Deduplicating alert %s (fingerprint=%s, last_sent=%.0fs ago)",
                alert.alert_id,
                fp,
                now - last_sent,
            )
            return []
        self._recent[fp] = now

        # Clean old dedup entries periodically
        if len(self._recent) > 10000:
            cutoff = now - self.dedup_window
            self._recent = {k: v for k, v in self._recent.items() if v > cutoff}
            logger.debug("Cleaned dedup cache, %d entries remaining", len(self._recent))

        # 3. Severity-based routing
        channels = self.routing_table.get(alert.severity, [Channel.SLACK])

        # 4. Circuit breaker filtering
        if self.enable_circuit_breaker:
            available_channels = []
            for channel in channels:
                cb = self._circuit_breakers.get(channel)
                if cb and not cb.can_execute():
                    logger.warning(
                        "Channel %s circuit breaker OPEN; skipping alert %s",
                        channel.value,
                        alert.alert_id,
                    )
                    continue
                available_channels.append(channel)
            channels = available_channels

        if not channels:
            logger.warning("All channels unavailable for alert %s", alert.alert_id)
            return []

        logger.info(
            "Routing alert %s (severity=%s, source=%s) to channels: %s",
            alert.alert_id,
            alert.severity.value,
            alert.source_service,
            [c.value for c in channels],
        )
        return channels

    def record_channel_success(self, channel: Channel) -> None:
        """Record a successful delivery on a channel."""
        if self.enable_circuit_breaker and channel in self._circuit_breakers:
            self._circuit_breakers[channel].record_success()

    def record_channel_failure(self, channel: Channel) -> None:
        """Record a failed delivery on a channel."""
        if self.enable_circuit_breaker and channel in self._circuit_breakers:
            self._circuit_breakers[channel].record_failure()

    def override_routing(
        self,
        severity: Severity,
        channels: list[Channel],
    ) -> None:
        """Temporarily override routing for a severity level.

        This is useful during incidents when specific channels need to be
        added or removed from the routing path.
        """
        old_channels = [c.value for c in self.routing_table.get(severity, [])]
        self.routing_table[severity] = channels
        logger.info(
            "Routing override: %s -> %s (was: %s)",
            severity.value,
            [c.value for c in channels],
            old_channels,
        )

    def get_circuit_breaker_status(self) -> dict[str, str]:
        """Return current state of all circuit breakers."""
        return {
            channel.value: cb.state
            for channel, cb in self._circuit_breakers.items()
        }
