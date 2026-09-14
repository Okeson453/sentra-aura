"""ClickHouse warehouse writer with batching and retry-safe failure handling."""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


class WarehouseWriter:
    """Async batch writer for the analytics warehouse."""

    def __init__(
        self,
        warehouse_url: str,
        batch_size: int = 100,
        flush_interval_seconds: int = 60,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.warehouse_url = warehouse_url
        self.batch_size = batch_size
        self.flush_interval = flush_interval_seconds
        self._buffer: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()
        self._client = client
        self._owns_client = client is None
        self._flush_task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        self._running = True
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                limits=httpx.Limits(max_connections=20),
            )
        self._flush_task = asyncio.create_task(self._periodic_flush())
        logger.info("WarehouseWriter started: url=%s", self.warehouse_url)

    async def stop(self) -> None:
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self._flush()
        if self._client and self._owns_client:
            await self._client.aclose()
        logger.info("WarehouseWriter stopped")

    async def write(self, record: dict[str, Any]) -> None:
        record = _serialize_datetimes(record)
        async with self._lock:
            self._buffer.append(record)
            should_flush = len(self._buffer) >= self.batch_size
        if should_flush:
            await self._flush()

    async def write_metrics(self, metrics: Any) -> None:
        """Write a dataclass or dict to the warehouse."""
        if hasattr(metrics, "__dataclass_fields__"):
            record = asdict(metrics)
        else:
            record = dict(metrics)
        await self.write(_serialize_datetimes(record))

    async def flush(self) -> None:
        """Persist all buffered records, raising if the warehouse rejects them."""
        await self._flush()

    async def _periodic_flush(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self.flush_interval)
                await self._flush()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Periodic flush error: %s", exc)

    async def _flush(self) -> None:
        async with self._lock:
            if not self._buffer:
                return
            batch = self._buffer[:]
            self._buffer = []

        try:
            if self._client is None:
                raise RuntimeError("Warehouse client is not initialized")
            endpoint, database = _clickhouse_endpoint(self.warehouse_url)
            query = f"INSERT INTO {database}.content_performance FORMAT JSONEachRow"
            payload = "\n".join(json.dumps(record, separators=(",", ":")) for record in batch)
            response = await self._client.post(
                endpoint,
                params={"query": query, "input_format_skip_unknown_fields": 1},
                content=payload,
                headers={"Content-Type": "application/x-ndjson"},
            )
            response.raise_for_status()
            logger.info("Flushed %d records to warehouse", len(batch))
        except Exception:
            logger.exception("Warehouse flush failed")
            # Preserve both failed records and anything queued concurrently.
            async with self._lock:
                self._buffer = batch + self._buffer
            raise


def _clickhouse_endpoint(warehouse_url: str) -> tuple[str, str]:
    parsed = urlparse(warehouse_url)
    if parsed.scheme not in {"clickhouse", "http", "https"} or not parsed.hostname:
        raise ValueError(f"Unsupported warehouse URL: {warehouse_url}")
    scheme = "http" if parsed.scheme == "clickhouse" else parsed.scheme
    port = f":{parsed.port}" if parsed.port else ""
    database = parsed.path.strip("/") or "default"
    return f"{scheme}://{parsed.hostname}{port}", database


def _serialize_datetimes(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _serialize_datetimes(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize_datetimes(v) for v in obj]
    return obj
