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
    dlq_stream_name: str = "SENTRAURA_DLQ"
    dlq_subject: str = "sentra.platform.dlq"


class MockNATSClient:
    """In-process stand-in used only when mock_mode=True (tests / local offline)."""

    def __init__(self) -> None:
        self.published: list[tuple[str, bytes]] = []
        self._subs: dict[str, list[Any]] = {}

    async def publish(self, subject: str, payload: bytes) -> None:
        self.published.append((subject, payload))
        for pattern, callbacks in self._subs.items():
            if _subject_matches(subject, pattern):
                for cb in callbacks:
                    delivered = _MockMsg(subject, payload)
                    result = cb(delivered)
                    if asyncio.iscoroutine(result):
                        await result

    async def subscribe(self, subject: str, cb: Any = None, **kwargs: Any) -> None:
        if cb is not None:
            self._subs.setdefault(subject, []).append(cb)

    def jetstream(self) -> "MockNATSClient":
        return self

    async def add_stream(self, config: Any = None) -> None:
        return None

    async def close(self) -> None:
        return None


class _MockMsg:
    """Minimal message stub so consumer callbacks work against the mock."""

    def __init__(self, subject: str, data: bytes) -> None:
        self.subject = subject
        self.data = data
        self.acked = False
        self.naked = False

    async def ack(self) -> None:
        self.acked = True

    async def nak(self) -> None:
        self.naked = True


def _subject_matches(subject: str, pattern: str) -> bool:
    if pattern == subject:
        return True
    if pattern.endswith(".>"):
        return subject.startswith(pattern[:-2])
    if pattern.endswith(".*"):
        return subject.startswith(pattern[:-1])
    return False


async def ensure_dlq_stream(
    nats_client: Any,
    *,
    stream_name: str = "SENTRAURA_DLQ",
    dlq_subject: str = "sentra.platform.dlq",
) -> bool:
    """Bind a JetStream stream to the dead-letter subject.

    ``EventConsumer`` writes failures to a plain subject. Without a stream
    bound to that subject the write is a core-NATS publish: it reaches any
    *currently connected* subscriber and is then discarded, so a failed event
    is lost the moment nobody is listening. Binding a stream is what makes the
    DLQ durable and replayable. Returns True when a stream was ensured.
    """
    try:
        from nats.js.api import RetentionPolicy, StorageType, StreamConfig
    except ImportError:  # pragma: no cover - dependency guarded elsewhere
        return False

    js_getter = getattr(nats_client, "jetstream", None)
    if js_getter is None:
        return False
    try:
        js = js_getter()
    except Exception:
        return False
    if js is None or not hasattr(js, "add_stream"):
        return False
    try:
        await js.add_stream(
            StreamConfig(
                name=stream_name,
                subjects=[dlq_subject],
                retention=RetentionPolicy.WORK_QUEUE,
                storage=StorageType.FILE,
                max_msgs=100_000,
            )
        )
        logger.info("DLQ stream %s bound to %s", stream_name, dlq_subject)
        return True
    except Exception as exc:
        msg = str(exc).lower()
        if "already in use" in msg or "already exists" in msg:
            logger.info("DLQ stream %s already exists", stream_name)
            return True
        logger.warning("Could not ensure DLQ stream %s: %s", stream_name, exc)
        return False


async def connect_nats(config: NATSClientConfig | None = None) -> Any:
    """Connect to NATS and optionally ensure a JetStream stream exists.

    Returns a live ``nats.NATS`` client (or ``MockNATSClient`` when mock_mode).
    Raises ``RuntimeError`` if the transport cannot be established and mock_mode
    is false \u2014 fail closed rather than silently dropping events.
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
                # The dead-letter subject is not covered by the main stream's
                # subjects, so it needs its own stream or DLQ writes are lost.
                await ensure_dlq_stream(
                    nc,
                    stream_name=cfg.dlq_stream_name,
                    dlq_subject=cfg.dlq_subject,
                )
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
