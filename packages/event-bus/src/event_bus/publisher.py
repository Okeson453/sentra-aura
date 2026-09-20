"""Event publisher for SentraAura.

Publishes validated events to NATS JetStream subjects.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from sentinel_exceptions import SchemaValidationError
from event_bus.schema_validator import SchemaValidator

logger = logging.getLogger(__name__)


class EventPublisher:
    """Publish events to NATS JetStream with schema validation."""

    def __init__(
        self,
        nats_client: Any,
        validator: SchemaValidator,
        *,
        default_subject_prefix: str = "sentra",
    ) -> None:
        self.nats = nats_client
        self.validator = validator
        self.prefix = default_subject_prefix

    def _subject(self, channel_id: str, event_family: str, event_type: str) -> str:
        return f"{self.prefix}.{channel_id}.{event_family}.{event_type}"

    def _jetstream(self) -> Any | None:
        """Return a JetStream context when the transport provides one.

        Publishing through JetStream (rather than core NATS) is what makes an
        event durable and broker-acknowledged. The transport is duck-typed, so
        a client without JetStream falls back to core publish instead of
        failing outright.
        """
        jetstream = getattr(self.nats, "jetstream", None)
        if jetstream is None:
            return None
        try:
            return jetstream()
        except Exception as exc:  # pragma: no cover - transport specific
            logger.debug("JetStream context unavailable, using core publish: %s", exc)
            return None

    async def _publish_to_subject(self, subject: str, event: dict[str, Any]) -> None:
        """Publish an already-validated event, preferring the durable path."""
        payload = json.dumps(event, default=str).encode()
        js = self._jetstream()
        if js is not None and hasattr(js, "publish"):
            ack = await js.publish(subject, payload)
            logger.debug(
                "published to JetStream subject=%s seq=%s",
                subject,
                getattr(ack, "seq", None),
            )
            return
        logger.warning(
            "JetStream context unavailable; publishing %s to core NATS (not durable)",
            subject,
        )
        await self.nats.publish(subject, payload)

    async def publish(
        self,
        event: dict[str, Any],
        *,
        channel_id: str,
        event_family: str,
        event_type: str,
        schema_name: str | None = None,
    ) -> None:
        """Validate and publish an event.

        Args:
            event: The event payload dictionary.
            channel_id: Channel identifier for subject routing.
            event_family: e.g. 'trend', 'script', 'clip', 'publication'.
            event_type: Specific event type.
            schema_name: Optional explicit schema name for validation.
        """
        schema = schema_name or f"{event_type}.json"
        is_valid, errors = self.validator.validate(event, schema)
        if not is_valid:
            raise SchemaValidationError(
                f"Event validation failed for {schema}",
                details={"errors": errors, "event_preview": str(event)[:200]},
            )

        subject = self._subject(channel_id, event_family, event_type)
        await self._publish_to_subject(subject, event)

    async def publish_platform(
        self,
        event: dict[str, Any],
        *,
        event_type: str,
    ) -> None:
        """Publish a platform-wide event (no channel prefix).

        Intentionally unvalidated: the caller has no channel-scoped schema.
        Prefer :meth:`publish` for anything that has a published contract.
        """
        subject = f"{self.prefix}.platform.{event_type}"
        await self._publish_to_subject(subject, event)
