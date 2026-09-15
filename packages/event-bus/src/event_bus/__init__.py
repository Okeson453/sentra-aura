"""SentraAura NATS JetStream event bus wrapper.

Publisher, consumer, schema validation, replay, and connection helpers.
"""
from event_bus.publisher import EventPublisher
from event_bus.consumer import EventConsumer
from event_bus.schema_validator import SchemaValidator
from event_bus.replay import EventReplay
from event_bus.client import (
    NATSClientConfig,
    MockNATSClient,
    connect_nats,
    create_event_publisher,
)

__all__ = [
    "EventPublisher",
    "EventConsumer",
    "SchemaValidator",
    "EventReplay",
    "NATSClientConfig",
    "MockNATSClient",
    "connect_nats",
    "create_event_publisher",
]
