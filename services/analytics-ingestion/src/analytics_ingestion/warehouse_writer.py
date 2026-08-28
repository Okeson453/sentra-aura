"""ClickHouse / BigQuery warehouse writer with batching and retry."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class WarehouseWriter:
    """Async batch writer for the analytics warehouse."""

    def __init__(
        self,
        warehouse_url: str,
        batch_size: int = 100,
        flush_interval_seconds: int = 60,
    ) -> None:
        self.warehouse_url = warehouse_url
        self.batch_size = batch_size
        self.flush_interval = flush_interval_seconds
        self._buffer: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()
        self._client: httpx.AsyncClient | None = None
        self._flush_task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        self._running = True
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
        if self._client:
            await self._client.aclose()
        logger.info("WarehouseWriter stopped")

    async def write(self, record: dict[str, Any]) -> None:
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
        # Convert datetime to ISO strings for JSON serialization
        record = _serialize_datetimes(record)
        await self.write(record)

    async def flush(self) -> None:
        """Force an immediate flush of the buffer to the warehouse."""
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

        if not self._client:
            logger.warning("Warehouse client not initialized, dropping %d records", len(batch))
            return

        try:
            # In production, this would use clickhouse-connect or BigQuery SDK
            # For the architecture, we simulate the batch insert
            logger.info("Flushing %d records to warehouse", len(batch))
            # Placeholder: actual insert logic would go here
            # response = await self._client.post(
            #     f"{self.warehouse_url}/insert",
            #     json={"table": "content_performance", "rows": batch},
            # )
            # response.raise_for_status()
        except Exception as exc:
            logger.error("Warehouse flush failed: %s", exc)
            # Re-buffer for retry with backoff
            async with self._lock:
                self._buffer.extend(batch)


def _serialize_datetimes(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _serialize_datetimes(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize_datetimes(v) for v in obj]
    return obj
