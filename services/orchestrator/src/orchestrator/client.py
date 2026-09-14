"""Temporal client wrapper for SentraAura."""
from __future__ import annotations

from temporalio.client import Client

from orchestrator.config import get_settings

_temporal_client: Client | None = None


async def get_temporal_client() -> Client:
    """Return a cached client connected to the configured Temporal namespace."""
    global _temporal_client
    if _temporal_client is None:
        settings = get_settings()
        _temporal_client = await Client.connect(
            settings.temporal_host,
            namespace=settings.temporal_namespace,
        )
    return _temporal_client
