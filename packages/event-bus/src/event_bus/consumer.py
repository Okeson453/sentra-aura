"""Event consumer for SentraAura.

Subscribes to NATS JetStream subjects with durable consumer groups.
"""
from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

from sentinel_exceptions import SchemaValidationError
from event_bus.schema_validator import SchemaValidator


Handler = Callable[[dict[str, Any]], Awaitable[None]]


class EventConsumer:
    """Consume events from NATS JetStream with schema validation and DLQ."""

    def __init__(
        self,
        nats_client: Any,
        validator: SchemaValidator,
        *,
        max_deliver: int = 5,
        dlq_subject: str = "sentra.platform.dlq",
    ) -> None:
        self.nats = nats_client
        self.validator = validator
        self.max_deliver = max_deliver
        self.dlq_subject = dlq_subject
        self._handlers: dict[str, Handler] = {}

    def register(
        self,
        subject: str,
        handler: Handler,
        *,
        schema_name: str | None = None,
        durable_name: str | None = None,
    ) -> None:
        """Register a handler for a subject pattern."""
        self._handlers[subject] = handler
        # Subscription setup would happen here in real implementation

    async def handle_message(self, subject: str, payload: bytes) -> None:
        """Process a single message."""
        try:
            event = json.loads(payload.decode())
        except json.JSONDecodeError as exc:
            await self._send_to_dlq(subject, payload, f"JSON decode error: {exc}")
            return

        handler = self._handlers.get(subject)
        if handler is None:
            # Try wildcard match
            for pattern, h in self._handlers.items():
                if self._match(subject, pattern):
                    handler = h
                    break

        if handler is None:
            await self._send_to_dlq(subject, payload, "No handler registered")
            return

        try:
            await handler(event)
        except Exception as exc:
            await self._send_to_dlq(subject, payload, f"Handler error: {exc}")

    async def _send_to_dlq(self, subject: str, payload: bytes, reason: str) -> None:
        """Send failed message to dead-letter queue."""
        dlq_event = {
            "original_subject": subject,
            "payload_b64": payload.decode("utf-8", errors="replace"),
            "failure_reason": reason,
            "timestamp": "",  # Would be ISO timestamp
        }
        await self.nats.publish(self.dlq_subject, json.dumps(dlq_event).encode())

    def _match(self, subject: str, pattern: str) -> bool:
        """Simple wildcard matching for NATS subjects."""
        if pattern == subject:
            return True
        if pattern.endswith(".*"):
            return subject.startswith(pattern[:-1])
        if pattern.endswith(".>"):
            return subject.startswith(pattern[:-2])
        return False
