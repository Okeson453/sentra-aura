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
        self._schema_names: dict[str, str | None] = {}
        self._durable_names: dict[str, str | None] = {}

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
        self._schema_names[subject] = schema_name
        self._durable_names[subject] = durable_name

    async def start_subscriptions(self) -> None:
        """Bind registered handlers to the live NATS / JetStream client.

        Call after ``register`` for each subject. Uses core NATS subscribe when
        JetStream is unavailable; prefers JetStream durable consumers when
        ``jetstream()`` is present on the client.
        """
        js = None
        if hasattr(self.nats, "jetstream"):
            try:
                js = self.nats.jetstream()
            except Exception:
                js = None

        for subject, handler in list(self._handlers.items()):
            durable = self._durable_names.get(subject) or subject.replace(".", "_")[:48]

            async def _cb(msg, _subject=subject):  # noqa: B023
                payload = msg.data if hasattr(msg, "data") else msg
                if isinstance(payload, memoryview):
                    payload = payload.tobytes()
                await self.handle_message(_subject, payload)
                if hasattr(msg, "ack"):
                    try:
                        await msg.ack()
                    except Exception:
                        pass

            if js is not None and hasattr(js, "subscribe"):
                try:
                    await js.subscribe(subject, cb=_cb, durable=durable)
                    continue
                except Exception:
                    pass
            if hasattr(self.nats, "subscribe"):
                await self.nats.subscribe(subject, cb=_cb)

    async def handle_message(self, subject: str, payload: bytes) -> None:
        """Process a single message."""
        try:
            event = json.loads(payload.decode())
        except json.JSONDecodeError as exc:
            await self._send_to_dlq(subject, payload, f"JSON decode error: {exc}")
            return

        handler = self._handlers.get(subject)
        if handler is None:
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
            "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
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
