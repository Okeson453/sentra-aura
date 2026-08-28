"""Per-agent, per-invocation cost attribution with budget enforcement and queryable aggregates."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CostRecord:
    """A single cost attribution record."""

    record_id: str
    provider_id: str
    channel_id: str
    task_type: str
    model: str | None
    estimated_cost_usd: float
    actual_cost_usd: float | None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


class CostTracker:
    """Tracks AI provider costs with per-channel budget awareness.

    Designed to be queried by control-plane-api cost routes.
    """

    def __init__(self, storage_backend: Any | None = None) -> None:
        self._records: list[CostRecord] = []
        self._storage = storage_backend
        self._daily_totals: dict[str, dict[str, float]] = {}
        self._lock = None  # asyncio.Lock set by caller if async needed

    def set_lock(self, lock: Any) -> None:
        self._lock = lock

    def can_spend(self, channel_id: str, estimated_cost: float, budget: float) -> bool:
        """Check if a channel can afford an estimated cost within its daily budget."""
        day_key = time.strftime("%Y-%m-%d")
        spent = self._daily_totals.get(day_key, {}).get(channel_id, 0.0)
        return (spent + estimated_cost) <= budget

    def record(
        self,
        provider_id: str,
        channel_id: str,
        task_type: str,
        estimated_cost: float,
        latency_ms: float,
        model: str | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        actual_cost: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CostRecord:
        """Record a cost attribution entry."""
        record = CostRecord(
            record_id=f"cost-{int(time.time() * 1000)}-{provider_id}",
            provider_id=provider_id,
            channel_id=channel_id,
            task_type=task_type,
            model=model,
            estimated_cost_usd=estimated_cost,
            actual_cost_usd=actual_cost,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            metadata=metadata or {},
        )
        self._records.append(record)

        # Update daily totals
        day_key = time.strftime("%Y-%m-%d", time.gmtime(record.timestamp))
        if day_key not in self._daily_totals:
            self._daily_totals[day_key] = {}
        self._daily_totals[day_key][channel_id] = (
            self._daily_totals[day_key].get(channel_id, 0.0) + estimated_cost
        )

        logger.info(
            "Cost recorded: provider=%s channel=%s task=%s cost=%.6f",
            provider_id, channel_id, task_type, estimated_cost,
        )

        # Persist if backend available
        if self._storage is not None:
            try:
                self._storage.save(record)
            except Exception as exc:
                logger.warning("Failed to persist cost record: %s", exc)

        return record

    def get_usage_report(
        self,
        from_timestamp: float | None = None,
        to_timestamp: float | None = None,
        channel_id: str | None = None,
    ) -> dict[str, Any]:
        """Generate a usage report queryable by control-plane-api."""
        filtered = self._records
        if from_timestamp is not None:
            filtered = [r for r in filtered if r.timestamp >= from_timestamp]
        if to_timestamp is not None:
            filtered = [r for r in filtered if r.timestamp <= to_timestamp]
        if channel_id is not None:
            filtered = [r for r in filtered if r.channel_id == channel_id]

        total_cost = sum(r.estimated_cost_usd for r in filtered)
        by_provider: dict[str, float] = {}
        by_model: dict[str, float] = {}
        by_channel: dict[str, float] = {}
        by_task: dict[str, float] = {}

        for r in filtered:
            by_provider[r.provider_id] = by_provider.get(r.provider_id, 0.0) + r.estimated_cost_usd
            if r.model:
                by_model[r.model] = by_model.get(r.model, 0.0) + r.estimated_cost_usd
            by_channel[r.channel_id] = by_channel.get(r.channel_id, 0.0) + r.estimated_cost_usd
            by_task[r.task_type] = by_task.get(r.task_type, 0.0) + r.estimated_cost_usd

        return {
            "total_cost_usd": round(total_cost, 6),
            "by_provider": {k: round(v, 6) for k, v in by_provider.items()},
            "by_model": {k: round(v, 6) for k, v in by_model.items()},
            "by_channel": {k: round(v, 6) for k, v in by_channel.items()},
            "by_task": {k: round(v, 6) for k, v in by_task.items()},
            "invocation_count": len(filtered),
            "total_tokens": sum(r.prompt_tokens + r.completion_tokens for r in filtered),
            "average_latency_ms": round(
                sum(r.latency_ms for r in filtered) / len(filtered), 2
            ) if filtered else 0.0,
        }

    def get_channel_daily_spend(self, channel_id: str, day: str | None = None) -> float:
        """Get daily spend for a channel (YYYY-MM-DD)."""
        day_key = day or time.strftime("%Y-%m-%d")
        return self._daily_totals.get(day_key, {}).get(channel_id, 0.0)

    def export_records(self, fmt: str = "json") -> str:
        """Export all records as JSON."""
        if fmt == "json":
            return json.dumps(
                [
                    {
                        "record_id": r.record_id,
                        "provider_id": r.provider_id,
                        "channel_id": r.channel_id,
                        "task_type": r.task_type,
                        "model": r.model,
                        "estimated_cost_usd": r.estimated_cost_usd,
                        "actual_cost_usd": r.actual_cost_usd,
                        "prompt_tokens": r.prompt_tokens,
                        "completion_tokens": r.completion_tokens,
                        "latency_ms": r.latency_ms,
                        "timestamp": r.timestamp,
                        "metadata": r.metadata,
                    }
                    for r in self._records
                ],
                indent=2,
            )
        raise ValueError(f"Unsupported export format: {fmt}")
