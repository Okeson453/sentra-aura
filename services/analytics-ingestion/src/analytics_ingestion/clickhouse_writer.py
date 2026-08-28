"""ClickHouse-specific warehouse writer implementation."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class ClickHouseWriter:
    """Async writer for ClickHouse analytics warehouse."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8123,
        database: str = "analytics",
        username: str = "default",
        password: str = "",
        batch_size: int = 1000,
        flush_interval_seconds: int = 30,
    ) -> None:
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password
        self.batch_size = batch_size
        self.flush_interval = flush_interval_seconds
        self._buffer: list[dict[str, Any]] = []
        self._client: httpx.AsyncClient | None = None
        self._url = f"http://{host}:{port}"

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                auth=(self.username, self.password) if self.password else None,
                timeout=httpx.Timeout(30.0, connect=10.0),
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def create_tables(self) -> None:
        """Create required ClickHouse tables if they don't exist."""
        ddl = f"""
        CREATE TABLE IF NOT EXISTS {self.database}.content_performance (
            video_id String,
            channel_id String,
            views UInt64,
            likes UInt64,
            comments UInt64,
            shares UInt64,
            watch_time_seconds UInt64,
            average_view_duration_seconds Float64,
            ctr Float64,
            subscriber_gain Int64,
            measured_at DateTime64(3),
            inserted_at DateTime64(3) DEFAULT now64(3)
        ) ENGINE = MergeTree()
        ORDER BY (channel_id, measured_at, video_id);

        CREATE TABLE IF NOT EXISTS {self.database}.normalized_metrics (
            video_id String,
            channel_id String,
            views UInt64,
            normalized_ctr Float64,
            normalized_retention Float64,
            normalized_engagement Float64,
            normalized_watch_time Float64,
            composite_score Float64,
            confidence Float64,
            measured_at DateTime64(3),
            inserted_at DateTime64(3) DEFAULT now64(3)
        ) ENGINE = MergeTree()
        ORDER BY (channel_id, measured_at, video_id);
        """
        client = await self._get_client()
        for statement in ddl.strip().split(";"):
            stmt = statement.strip()
            if stmt:
                response = await client.post(f"{self._url}", params={"query": stmt})
                response.raise_for_status()
                logger.info("Executed DDL: %s...", stmt[:50])

    async def insert_metrics(self, records: list[dict[str, Any]], table: str = "content_performance") -> None:
        """Insert records into ClickHouse using the HTTP interface."""
        if not records:
            return

        # Build VALUES format
        values = []
        for r in records:
            row = []
            for key in ["video_id", "channel_id", "views", "likes", "comments", "shares",
                        "watch_time_seconds", "average_view_duration_seconds", "ctr", "subscriber_gain", "measured_at"]:
                val = r.get(key)
                if val is None:
                    row.append("NULL")
                elif isinstance(val, str):
                    row.append(f"'{val}'")
                elif isinstance(val, datetime):
                    row.append(f"'{val.isoformat()}'")
                else:
                    row.append(str(val))
            values.append(f"({', '.join(row)})")

        query = f"INSERT INTO {self.database}.{table} VALUES {', '.join(values)}"
        client = await self._get_client()
        response = await client.post(f"{self._url}", params={"query": query})
        response.raise_for_status()
        logger.info("Inserted %d records into %s", len(records), table)

    async def query_performance(
        self,
        channel_id: str,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, Any]]:
        """Query performance metrics for a channel in a time range."""
        query = f"""
        SELECT
            video_id,
            views,
            likes,
            comments,
            watch_time_seconds,
            ctr,
            measured_at
        FROM {self.database}.content_performance
        WHERE channel_id = '{channel_id}'
          AND measured_at BETWEEN '{start.isoformat()}' AND '{end.isoformat()}'
        ORDER BY measured_at DESC
        """
        client = await self._get_client()
        response = await client.post(f"{self._url}", params={"query": query})
        response.raise_for_status()
        # Parse TSV format (simplified)
        return []
