"""Event consumer for SentraAura.

Subscribes to NATS JetStream subjects with durable consumer groups.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from event_bus.schema_validator import SchemaValidator

logger = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any]], Awaitable[None]]

_DURABLE_SAFE = re.compile(r"[^A-Za-z0-9_-]")


class EventConsumer:
    """Consume events from NATS JetStream with schema validation and DLQ.

    A message is acknowledged only when a handler completed successfully and,
    when a schema is registered for the subject, the payload validated against
    it. Anything else is negatively acknowledged (so JetStream can redeliver)
    and recorded on the dead-letter subject.
    """

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

    def _durable_for(self, subject: str) -> str:
        """Derive a valid JetStream durable name for a subject pattern.

        Wildcards (``*`` / ``>``) are not legal in a durable name; leaving them
        in makes ``js.subscribe`` fail, which previously fell back to core NATS
        and silently dropped durability.
        """
        cleaned = _DURABLE_SAFE.sub("_", subject).strip("_")
        return (cleaned or "consumer")[:48]

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
            durable = self._durable_names.get(subject) or self._durable_for(subject)

            async def _cb(msg, _subject=subject):  # noqa: B023
                payload = msg.data if hasattr(msg, "data") else msg
                if isinstance(payload, memoryview):
                    payload = payload.tobytes()
                processed = await self.handle_message(_subject, payload)
                if hasattr(msg, "ack"):
                    try:
                        if processed:
                            await msg.ack()
                        elif hasattr(msg, "nak"):
                            await msg.nak()
                    except Exception as exc:  # pragma: no cover - transport specific
                        logger.debug("ack/nak failed for %s: %s", _subject, exc)

            if js is not None and hasattr(js, "subscribe"):
                try:
                    await js.subscribe(subject, cb=_cb, durable=durable)
                    logger.info("subscribed (durable=%s) to %s", durable, subject)
                    continue
                except Exception as exc:
                    logger.warning(
                        "JetStream durable subscribe failed for %s (%s); "
                        "falling back to core NATS",
                        subject,
                        exc,
                    )
            if hasattr(self.nats, "subscribe"):
                await self.nats.subscribe(subject, cb=_cb)

    def _resolve_handler(self, subject: str) -> tuple[str | None, Handler | None]:
        """Find the handler for a subject, exact match first."""
        handler = self._handlers.get(subject)
        if handler is not None:
            return subject, handler
        for pattern, candidate in self._handlers.items():
            if self._match(subject, pattern):
                return pattern, candidate
        return None, None

    async def handle_message(self, subject: str, payload: bytes) -> bool:
        """Process a single message.

        Returns ``True`` only when a handler ran to completion for a payload
        that satisfied its registered schema. Every other outcome is a failure
        and is routed to the dead-letter subject.
        """
        try:
            event = json.loads(payload.decode())
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            await self._send_to_dlq(subject, payload, f"JSON decode error: {exc}")
            return False

        pattern, handler = self._resolve_handler(subject)
        if handler is None or pattern is None:
            await self._send_to_dlq(subject, payload, "No handler registered")
            return False

        schema_name = self._schema_names.get(pattern)
        if schema_name:
            is_valid, errors = self.validator.validate(event, schema_name)
            if not is_valid:
                await self._send_to_dlq(
                    subject,
                    payload,
                    f"Schema validation failed against {schema_name}: {errors}",
                )
                return False

        try:
            await handler(event)
        except Exception as exc:
            await self._send_to_dlq(subject, payload, f"Handler error: {exc}")
            return False
        return True

    async def _send_to_dlq(self, subject: str, payload: bytes, reason: str) -> None:
        """Send failed message to dead-letter queue."""
        if isinstance(payload, memoryview):
            payload = payload.tobytes()
        dlq_event = {
            "original_subject": subject,
            "payload_b64": payload.decode("utf-8", errors="replace"),
            "failure_reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        body = json.dumps(dlq_event).encode()
        js = None
        if hasattr(self.nats, "jetstream"):
            try:
                js = self.nats.jetstream()
            except Exception:
                js = None
        if js is not None and hasattr(js, "publish"):
            await js.publish(self.dlq_subject, body)
            return
        await self.nats.publish(self.dlq_subject, body)

    def _match(self, subject: str, pattern: str) -> bool:
        """Simple wildcard matching for NATS subjects."""
        if pattern == subject:
            return True
        if pattern.endswith(".>"):
            return subject.startswith(pattern[:-2])
        if pattern.endswith(".*"):
            return subject.startswith(pattern[:-1])
        return False
