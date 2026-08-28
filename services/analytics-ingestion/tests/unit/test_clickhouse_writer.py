"""Unit tests for ClickHouse writer."""
from __future__ import annotations

import pytest
from datetime import datetime

from analytics_ingestion.clickhouse_writer import ClickHouseWriter


def test_writer_initialization():
    writer = ClickHouseWriter(
        host="clickhouse.example.com",
        port=8123,
        database="analytics",
        username="sentra",
        password="secret",
    )
    assert writer.host == "clickhouse.example.com"
    assert writer.port == 8123
    assert writer.database == "analytics"


def test_writer_default_values():
    writer = ClickHouseWriter()
    assert writer.host == "localhost"
    assert writer.port == 8123
    assert writer.database == "analytics"
    assert writer.batch_size == 1000


@pytest.mark.asyncio
async def test_writer_close_without_client():
    writer = ClickHouseWriter()
    await writer.close()  # Should not raise
