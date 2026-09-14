"""Unit tests for warehouse writer."""
from __future__ import annotations

import json
from datetime import datetime

import httpx
import pytest

from analytics_ingestion.warehouse_writer import WarehouseWriter, _serialize_datetimes


@pytest.mark.asyncio
async def test_write_and_flush() -> None:
    requests: list[httpx.Request] = []

    async def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    writer = WarehouseWriter(
        warehouse_url="clickhouse://localhost:8123/analytics",
        batch_size=2,
        flush_interval_seconds=60,
        client=client,
    )
    await writer.start()
    try:
        await writer.write({"video_id": "v1", "ts": datetime(2024, 1, 1)})
        await writer.write({"video_id": "v2", "ts": datetime(2024, 1, 2)})
        assert writer._buffer == []
        assert len(requests) == 1
        assert requests[0].url.params["query"] == (
            "INSERT INTO analytics.content_performance FORMAT JSONEachRow"
        )
        rows = [json.loads(line) for line in requests[0].content.decode().splitlines()]
        assert [row["video_id"] for row in rows] == ["v1", "v2"]
    finally:
        await writer.stop()
        await client.aclose()


@pytest.mark.asyncio
async def test_failed_flush_is_raised_and_rebuffers_records() -> None:
    async def fail(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(fail))
    writer = WarehouseWriter(
        warehouse_url="clickhouse://localhost:8123/analytics",
        batch_size=100,
        client=client,
    )
    writer._client = client
    await writer.write({"video_id": "v1"})

    with pytest.raises(httpx.HTTPStatusError):
        await writer.flush()

    assert writer._buffer == [{"video_id": "v1"}]
    await client.aclose()


def test_serialize_datetimes() -> None:
    now = datetime(2024, 1, 15, 12, 0, 0)
    result = _serialize_datetimes({"created_at": now, "nested": {"updated": now}, "count": 5})
    assert result["created_at"] == "2024-01-15T12:00:00"
    assert result["nested"]["updated"] == "2024-01-15T12:00:00"
    assert result["count"] == 5
