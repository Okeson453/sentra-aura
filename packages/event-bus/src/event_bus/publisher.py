"""Event publisher for SentraAura.

Publishes validated events to NATS JetStream subjects.
"""
from __future__ import annotations

import json
from typing import Any

from sentinel_exceptions import SchemaValidationError
from event_bus.schema_validator import SchemaValidator


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
        payload = json.dumps(event, default=str).encode()

        # Publish to NATS JetStream
        await self.nats.publish(subject, payload)

    async def publish_platform(
        self,
        event: dict[str, Any],
        *,
        event_type: str,
    ) -> None:
        """Publish a platform-wide event (no channel prefix)."""
        subject = f"{self.prefix}.platform.{event_type}"
        payload = json.dumps(event, default=str).encode()
        await self.nats.publish(subject, payload)
