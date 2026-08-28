"""Unit tests for warehouse writer."""
from __future__ import annotations

import asyncio
import pytest

from analytics_ingestion.warehouse_writer import WarehouseWriter, _serialize_datetimes
from datetime import datetime


@pytest.mark.asyncio
async def test_write_and_flush():
    writer = WarehouseWriter(warehouse_url="http://localhost:8123", batch_size=2, flush_interval_seconds=60)
    await writer.start()
    try:
        await writer.write({"test": "data", "ts": datetime.utcnow()})
        await writer.write({"test": "data2", "ts": datetime.utcnow()})
        # Batch of 2 should trigger flush (but warehouse is mocked)
        assert len(writer._buffer) == 0  # Flushed
    finally:
        await writer.stop()


def test_serialize_datetimes():
    now = datetime(2024, 1, 15, 12, 0, 0)
    result = _serialize_datetimes({"created_at": now, "nested": {"updated": now}, "count": 5})
    assert result["created_at"] == "2024-01-15T12:00:00"
    assert result["nested"]["updated"] == "2024-01-15T12:00:00"
    assert result["count"] == 5
