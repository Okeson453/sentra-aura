"""Temporal client wrapper for SentraAura."""
from __future__ import annotations

from temporalio.client import Client

_temporal_client: Client | None = None


async def get_temporal_client() -> Client:
    global _temporal_client
    if _temporal_client is None:
        _temporal_client = await Client.connect("localhost:7233")
    return _temporal_client
