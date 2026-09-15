"""NATS JetStream publisher for normalized events.

Supports stream creation, async publish, batch publish, DLQ,
and exactly-once semantics via JetStream.
Matches Architecture §6.2 and Backend Spec §6.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from data_ingestion_pipeline.models import NormalizedEvent

logger = logging.getLogger(__name__)


@dataclass
class PublishResult:
    """Result of a publish operation."""

    success: bool
    event_id: str
    seq: int | None = None
    error: str | None = None
    retry_count: int = 0


@dataclass
class NATSConfig:
    """Configuration for NATS JetStream connection."""

    servers: list[str] = field(default_factory=lambda: ["nats://localhost:4222"])
    stream_name: str = "SENTRAURA_EVENTS"
    subjects: list[str] = field(default_factory=lambda: ["sentraura.events.>"])
    max_msgs: int = 1_000_000
    max_bytes: int = 10 * 1024 * 1024 * 1024  # 10GB
    retention: str = "limits"
    storage: str = "file"
    replicas: int = 1
    max_age_seconds: int = 7 * 24 * 3600  # 7 days
    dlq_subject: str = "sentraura.events.dlq"
    dlq_stream: str = "SENTRAURA_DLQ"
    max_publish_retries: int = 3
    max_connect_attempts: int = 3
    connect_timeout_seconds: float = 1.0
    reconnect_wait_seconds: float = 0.25
    mock_mode: bool = False


class NATSPublisher:
    """NATS JetStream publisher with DLQ support."""

    def __init__(self, config: NATSConfig | None = None) -> None:
        self.config = config or NATSConfig()
        self._nc: Any = None
        self._js: Any = None
        self._connected = False
        self._connect_lock = asyncio.Lock()
        self._connection_error: str | None = None

    @property
    def is_ready(self) -> bool:
        """Return whether publishing is intentionally available."""
        return self.config.mock_mode or (self._connected and self._js is not None)

    async def connect(self) -> None:
        """Connect to NATS and initialize JetStream with bounded retries."""
        if self.is_ready:
            return
        if self.config.mock_mode:
            self._connected = True
            logger.warning("NATS explicit mock mode enabled; events will not leave the process")
            return

        async with self._connect_lock:
            if self.is_ready:
                return
            try:
                import nats
                from nats.js.api import RetentionPolicy, StorageType, StreamConfig
            except ImportError as exc:
                self._connection_error = f"NATS transport unavailable: {exc}"
                raise RuntimeError(self._connection_error) from exc

            attempts = max(1, self.config.max_connect_attempts)
            last_error: Exception | None = None
            for attempt in range(1, attempts + 1):
                try:
                    self._nc = await asyncio.wait_for(
                        nats.connect(
                            servers=self.config.servers,
                            allow_reconnect=True,
                            max_reconnect_attempts=0,
                            connect_timeout=self.config.connect_timeout_seconds,
                        ),
                        timeout=self.config.connect_timeout_seconds + 0.5,
                    )
                    self._js = self._nc.jetstream()
                    await self._ensure_streams(StreamConfig, RetentionPolicy, StorageType)
                    self._connected = True
                    self._connection_error = None
                    logger.info("NATS JetStream publisher connected")
                    return
                except Exception as exc:
                    last_error = exc
                    self._connected = False
                    self._js = None
                    if self._nc is not None:
                        try:
                            await self._nc.close()
                        except Exception:
                            logger.debug("Failed to close unsuccessful NATS connection", exc_info=True)
                        self._nc = None
                    if attempt < attempts:
                        delay = self.config.reconnect_wait_seconds * (2 ** (attempt - 1))
                        await asyncio.sleep(delay * random.uniform(0.5, 1.5))

            self._connection_error = (
                f"NATS connection failed after {attempts} attempts: {last_error}"
            )
            logger.error(self._connection_error)
            raise RuntimeError(self._connection_error) from last_error

    async def _ensure_streams(self, stream_config: Any, retention: Any, storage: Any) -> None:
        """Ensure the primary and dead-letter streams exist."""
        try:
            await self._js.add_stream(
                stream_config(
                    name=self.config.stream_name,
                    subjects=self.config.subjects,
                    max_msgs=self.config.max_msgs,
                    max_bytes=self.config.max_bytes,
                    retention=retention.LIMITS,
                    storage=storage.FILE,
                    replicas=self.config.replicas,
                    max_age=self.config.max_age_seconds,
                )
            )
            logger.info("Created JetStream stream %s", self.config.stream_name)
        except Exception as exc:
            if "already in use" not in str(exc).lower():
                raise
            logger.info("Stream %s already exists", self.config.stream_name)

        try:
            await self._js.add_stream(
                stream_config(
                    name=self.config.dlq_stream,
                    subjects=[self.config.dlq_subject],
                    retention=retention.WORK_QUEUE,
                    storage=storage.FILE,
                    max_msgs=100_000,
                )
            )
            logger.info("Created DLQ stream %s", self.config.dlq_stream)
        except Exception as exc:
            if "already in use" not in str(exc).lower():
                raise
            logger.info("DLQ stream %s already exists", self.config.dlq_stream)

    async def publish(self, subject: str, event: NormalizedEvent) -> PublishResult:
        """Publish a single event to JetStream with retry and DLQ fallback."""
        if self.config.mock_mode:
            if not self._connected:
                await self.connect()
            return PublishResult(
                success=True,
                event_id=event.event_id,
                error="mock mode: event was not sent to NATS",
            )

        if not self._connected:
            try:
                await self.connect()
            except Exception as exc:
                return PublishResult(success=False, event_id=event.event_id, error=str(exc))

        if self._js is None:
            error = self._connection_error or "NATS JetStream context unavailable"
            return PublishResult(success=False, event_id=event.event_id, error=error)

        payload = json.dumps({
            "event_id": event.event_id,
            "source": event.source,
            "event_type": event.event_type,
            "channel_id": event.channel_id,
            "tenant_id": event.tenant_id,
            "payload": event.payload,
            "normalized_at": event.normalized_at.isoformat() if event.normalized_at else None,
            "metadata": event.metadata,
        }).encode()

        attempts = max(1, self.config.max_publish_retries)
        for attempt in range(attempts):
            try:
                ack = await self._js.publish(subject, payload)
                return PublishResult(
                    success=True,
                    event_id=event.event_id,
                    seq=ack.seq,
                    retry_count=attempt,
                )
            except Exception as exc:
                logger.warning(
                    "Publish attempt %s failed for %s: %s", attempt + 1, event.event_id, exc
                )
                if attempt < attempts - 1:
                    await asyncio.sleep(2**attempt)
                else:
                    await self._send_to_dlq(event, str(exc))
                    return PublishResult(
                        success=False,
                        event_id=event.event_id,
                        error=str(exc),
                        retry_count=attempt,
                    )

        return PublishResult(success=False, event_id=event.event_id, error="Max retries exceeded")

    async def publish_batch(
        self, subject: str, events: list[NormalizedEvent]
    ) -> list[PublishResult]:
        """Publish a batch of events concurrently."""
        if not events:
            return []
        if not self.config.mock_mode and not self._connected:
            try:
                await self.connect()
            except Exception as exc:
                return [
                    PublishResult(success=False, event_id=event.event_id, error=str(exc))
                    for event in events
                ]

        semaphore = asyncio.Semaphore(50)

        async def _pub(event: NormalizedEvent) -> PublishResult:
            async with semaphore:
                try:
                    return await self.publish(subject, event)
                except Exception as exc:
                    return PublishResult(success=False, event_id=event.event_id, error=str(exc))

        return await asyncio.gather(*(_pub(event) for event in events))

    async def _send_to_dlq(self, event: NormalizedEvent, error: str) -> None:
        """Send a failed event to the dead-letter queue when JetStream is available."""
        if self._js is None:
            logger.error("Cannot send event %s to DLQ: NATS is unavailable", event.event_id)
            return
        try:
            payload = json.dumps({
                "original_event": {
                    "event_id": event.event_id,
                    "source": event.source,
                    "event_type": event.event_type,
                    "payload": event.payload,
                },
                "error": error,
                "failed_at": datetime.now(timezone.utc).isoformat(),
                "retry_count": self.config.max_publish_retries,
            }).encode()
            await self._js.publish(self.config.dlq_subject, payload)
            logger.info("Sent event %s to DLQ", event.event_id)
        except Exception as exc:
            logger.error("DLQ publish failed for %s: %s", event.event_id, exc)

    async def close(self) -> None:
        """Close the NATS connection."""
        if self._nc:
            await self._nc.close()
        self._nc = None
        self._js = None
        self._connected = False
        logger.info("NATS connection closed")
