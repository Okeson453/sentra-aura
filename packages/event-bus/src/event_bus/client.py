"""NATS connection helpers for SentraAura event-bus.

Services must call ``connect_nats`` (or pass an existing client) before
constructing ``EventPublisher`` / ``EventConsumer``. Without this, the
package only held abstract wrappers and was never wired to real NATS (P0-07).
"""
from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class NATSClientConfig:
    """Connection settings for NATS / JetStream."""

    servers: list[str] = field(default_factory=lambda: ["nats://localhost:4222"])
    max_connect_attempts: int = 3
    connect_timeout_seconds: float = 2.0
    reconnect_wait_seconds: float = 0.25
    mock_mode: bool = False
    stream_name: str = "SENTRAURA_EVENTS"
    subjects: list[str] = field(default_factory=lambda: ["sentra.>", "sentraura.>"])
    ensure_stream: bool = True


class MockNATSClient:
    """In-process stand-in used only when mock_mode=True (tests / local offline)."""

    def __init__(self) -> None:
        self.published: list[tuple[str, bytes]] = []

    async def publish(self, subject: str, payload: bytes) -> None:
        self.published.append((subject, payload))

    def jetstream(self) -> "MockNATSClient":
        return self

    async def close(self) -> None:
        return None


async def connect_nats(config: NATSClientConfig | None = None) -> Any:
    """Connect to NATS and optionally ensure a JetStream stream exists.

    Returns a live ``nats.NATS`` client (or ``MockNATSClient`` when mock_mode).
    Raises ``RuntimeError`` if the transport cannot be established and mock_mode
    is false — fail closed rather than silently dropping events.
    """
    cfg = config or NATSClientConfig()
    if cfg.mock_mode:
        logger.warning("NATS mock_mode enabled; events stay in-process")
        return MockNATSClient()

    try:
        import nats
        from nats.js.api import RetentionPolicy, StorageType, StreamConfig
    except ImportError as exc:
        raise RuntimeError(
            "nats-py is required for real event-bus connections; "
            "install nats-py or set mock_mode=True for tests"
        ) from exc

    last_error: Exception | None = None
    attempts = max(1, cfg.max_connect_attempts)
    for attempt in range(1, attempts + 1):
        nc = None
        try:
            nc = await asyncio.wait_for(
                nats.connect(
                    servers=cfg.servers,
                    allow_reconnect=True,
                    max_reconnect_attempts=60,
                    connect_timeout=cfg.connect_timeout_seconds,
                ),
                timeout=cfg.connect_timeout_seconds + 1.0,
            )
            if cfg.ensure_stream:
                js = nc.jetstream()
                try:
                    await js.add_stream(
                        StreamConfig(
                            name=cfg.stream_name,
                            subjects=list(cfg.subjects),
                            retention=RetentionPolicy.LIMITS,
                            storage=StorageType.FILE,
                            max_msgs=1_000_000,
                            max_bytes=10 * 1024 * 1024 * 1024,
                        )
                    )
                except Exception as stream_exc:
                    msg = str(stream_exc).lower()
                    if "already in use" not in msg and "already exists" not in msg and "name" not in msg:
                        logger.debug("stream ensure note: %s", stream_exc)
            logger.info("event-bus connected to NATS servers=%s", cfg.servers)
            return nc
        except Exception as exc:
            last_error = exc
            if nc is not None:
                try:
                    await nc.close()
                except Exception:
                    pass
            if attempt < attempts:
                delay = cfg.reconnect_wait_seconds * (2 ** (attempt - 1))
                await asyncio.sleep(delay * random.uniform(0.5, 1.5))

    raise RuntimeError(
        f"NATS connection failed after {attempts} attempts: {last_error}"
    )


async def create_event_publisher(
    *,
    nats_url: str = "nats://localhost:4222",
    mock_mode: bool = False,
    schema_dir: str | None = None,
) -> tuple[Any, Any]:
    """Convenience: connect NATS + build EventPublisher with SchemaValidator.

    Returns ``(nats_client, EventPublisher)``.
    """
    from event_bus.publisher import EventPublisher
    from event_bus.schema_validator import SchemaValidator

    cfg = NATSClientConfig(
        servers=[nats_url] if isinstance(nats_url, str) else list(nats_url),
        mock_mode=mock_mode,
    )
    nc = await connect_nats(cfg)
    validator = SchemaValidator(schemas_dir=schema_dir) if schema_dir else SchemaValidator()
    publisher = EventPublisher(nc, validator)
    return nc, publisher
