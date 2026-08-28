"""Event replay for SentraAura.

Replay events from NATS JetStream by offset or timestamp.
"""
from __future__ import annotations

from typing import Any


class EventReplay:
    """Replay historical events for state reconstruction."""

    def __init__(self, nats_client: Any) -> None:
        self.nats = nats_client

    async def replay_from_offset(
        self,
        subject: str,
        offset: int,
        handler: Any,
        *,
        batch_size: int = 100,
    ) -> int:
        """Replay events from a given stream offset.

        Returns the number of events replayed.
        """
        # In real implementation: JetStream consumer with DeliverByStartSequence
        return 0

    async def replay_from_timestamp(
        self,
        subject: str,
        timestamp: str,
        handler: Any,
        *,
        batch_size: int = 100,
    ) -> int:
        """Replay events from a given ISO timestamp.

        Returns the number of events replayed.
        """
        # In real implementation: JetStream consumer with DeliverByStartTime
        return 0
