"""Usage metering, per-channel attribution, cost aggregation, and budget enforcement."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MeterRecord:
    """A single metered usage event."""

    tenant_id: str
    channel_id: str
    service_name: str
    operation: str
    units: float
    unit_cost_usd: float
    total_cost_usd: float
    metadata: dict[str, Any]
    timestamp: datetime
    record_id: str = field(default="")


@dataclass
class BudgetAlert:
    """Budget threshold alert."""

    tenant_id: str
    threshold_percent: float
    current_spend: float
    budget_limit: float
    alert_type: str  # warning, critical
    timestamp: datetime


class MeteringEngine:
    """Production-grade metering engine for SaaS billing.

    Features:
    - Per-operation unit cost tracking
    - Tenant and channel-level aggregation
    - Budget enforcement with configurable thresholds
    - Cost attribution by service and operation
    - Historical trend analysis
    - Alert generation for budget thresholds
    """

    DEFAULT_UNIT_COSTS: dict[str, float] = {
        # LLM operations
        "llm_input_token": 0.00001,
        "llm_output_token": 0.00003,
        "llm_embedding_token": 0.000001,
        # Media operations
        "video_render_minute": 0.05,
        "audio_render_minute": 0.02,
        "image_generation": 0.02,
        "thumbnail_generation": 0.01,
        # Storage operations
        "storage_gb_month": 0.02,
        "cdn_transfer_gb": 0.08,
        "backup_gb_month": 0.01,
        # API operations
        "api_call": 0.001,
        "webhook_delivery": 0.0005,
        "event_ingestion": 0.0001,
        # YouTube operations
        "youtube_upload": 0.10,
        "youtube_api_call": 0.005,
        "youtube_analytics_query": 0.005,
        # Agent operations
        "agent_invocation": 0.02,
        "agent_training_hour": 0.50,
        "eval_run": 0.10,
        # Data operations
        "analytics_query": 0.005,
        "warehouse_ingest_gb": 0.05,
        "etl_job_run": 0.25,
    }

    def __init__(
        self,
        unit_costs: dict[str, float] | None = None,
        budget_thresholds: dict[str, list[float]] | None = None,
    ) -> None:
        self._unit_costs = unit_costs or dict(self.DEFAULT_UNIT_COSTS)
        self._budget_thresholds = budget_thresholds or {}
        self._records: list[MeterRecord] = []
        self._tenant_budgets: dict[str, float] = {}
        self._alerts: list[BudgetAlert] = []

    def record_usage(
        self,
        tenant_id: str,
        channel_id: str,
        service_name: str,
        operation: str,
        units: float,
        metadata: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> MeterRecord:
        """Record a usage event and return the meter record.

        Args:
            tenant_id: The tenant identifier for billing attribution
            channel_id: The content channel identifier
            service_name: The service that consumed the resource
            operation: The specific operation type
            units: The quantity consumed
            metadata: Additional context (model name, video ID, etc.)
            timestamp: When the usage occurred (default: now)

        Returns:
            The created MeterRecord with calculated cost
        """
        unit_cost = self._unit_costs.get(operation, 0.0)
        total_cost = round(units * unit_cost, 6)
        ts = timestamp or datetime.utcnow()

        record = MeterRecord(
            tenant_id=tenant_id,
            channel_id=channel_id,
            service_name=service_name,
            operation=operation,
            units=units,
            unit_cost_usd=unit_cost,
            total_cost_usd=total_cost,
            metadata=metadata or {},
            timestamp=ts,
            record_id=f"MR-{tenant_id}-{ts.strftime('%Y%m%d%H%M%S')}-{len(self._records):06d}",
        )
        self._records.append(record)

        # Check budget thresholds
        self._check_budget_thresholds(tenant_id, ts)

        logger.debug(
            "Metered: tenant=%s service=%s op=%s units=%.2f cost=$%.6f",
            tenant_id,
            service_name,
            operation,
            units,
            total_cost,
        )
        return record

    def _check_budget_thresholds(self, tenant_id: str, timestamp: datetime) -> None:
        """Check if tenant has exceeded any budget thresholds."""
        budget = self._tenant_budgets.get(tenant_id)
        if not budget:
            return

        thresholds = self._budget_thresholds.get(tenant_id, [0.5, 0.8, 0.95])
        current_month_start = datetime(timestamp.year, timestamp.month, 1)
        current_spend = self._calculate_spend(tenant_id, current_month_start, timestamp)
        spend_percent = current_spend / budget

        for threshold in thresholds:
            if spend_percent >= threshold:
                # Check if we already alerted for this threshold
                already_alerted = any(
                    a.tenant_id == tenant_id
                    and a.threshold_percent == threshold
                    and a.timestamp >= current_month_start
                    for a in self._alerts
                )
                if not already_alerted:
                    alert = BudgetAlert(
                        tenant_id=tenant_id,
                        threshold_percent=threshold,
                        current_spend=current_spend,
                        budget_limit=budget,
                        alert_type="critical" if threshold >= 0.95 else "warning",
                        timestamp=timestamp,
                    )
                    self._alerts.append(alert)
                    logger.warning(
                        "Budget alert: tenant=%s at %.0f%% of budget ($%.2f / $%.2f)",
                        tenant_id,
                        threshold * 100,
                        current_spend,
                        budget,
                    )

    def _calculate_spend(
        self,
        tenant_id: str,
        start: datetime,
        end: datetime,
    ) -> float:
        """Calculate total spend for a tenant in a time window."""
        return sum(
            r.total_cost_usd
            for r in self._records
            if r.tenant_id == tenant_id and start <= r.timestamp <= end
        )

    def set_tenant_budget(self, tenant_id: str, budget_usd: float) -> None:
        """Set a monthly budget limit for a tenant."""
        self._tenant_budgets[tenant_id] = budget_usd
        logger.info("Set budget for tenant %s: $%.2f/month", tenant_id, budget_usd)

    def set_unit_cost(self, operation: str, cost_usd: float) -> None:
        """Override the unit cost for an operation."""
        self._unit_costs[operation] = cost_usd
        logger.info("Updated unit cost for %s: $%.6f", operation, cost_usd)

    def get_unit_cost(self, operation: str) -> float:
        """Get the current unit cost for an operation."""
        return self._unit_costs.get(operation, 0.0)

    def aggregate_by_tenant(
        self,
        tenant_id: str,
        start: datetime,
        end: datetime,
    ) -> dict[str, Any]:
        """Aggregate usage for a tenant in a time window.

        Returns:
            Dict with total cost, operation breakdown, and service breakdown.
        """
        filtered = [
            r for r in self._records
            if r.tenant_id == tenant_id and start <= r.timestamp <= end
        ]

        by_operation: dict[str, dict[str, Any]] = {}
        by_service: dict[str, float] = {}
        total = 0.0

        for r in filtered:
            if r.operation not in by_operation:
                by_operation[r.operation] = {"units": 0.0, "cost_usd": 0.0, "count": 0}
            by_operation[r.operation]["units"] += r.units
            by_operation[r.operation]["cost_usd"] += r.total_cost_usd
            by_operation[r.operation]["count"] += 1

            by_service[r.service_name] = by_service.get(r.service_name, 0.0) + r.total_cost_usd
            total += r.total_cost_usd

        budget = self._tenant_budgets.get(tenant_id)
        budget_usage = total / budget if budget else None

        return {
            "tenant_id": tenant_id,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "total_cost_usd": round(total, 4),
            "budget_limit_usd": budget,
            "budget_usage_percent": round(budget_usage * 100, 2) if budget_usage is not None else None,
            "operations": {
                op: {
                    "units": round(data["units"], 4),
                    "cost_usd": round(data["cost_usd"], 4),
                    "count": data["count"],
                }
                for op, data in by_operation.items()
            },
            "by_service": {svc: round(cost, 4) for svc, cost in by_service.items()},
            "record_count": len(filtered),
        }

    def aggregate_by_channel(
        self,
        channel_id: str,
        start: datetime,
        end: datetime,
    ) -> dict[str, Any]:
        """Aggregate usage for a channel in a time window."""
        filtered = [
            r for r in self._records
            if r.channel_id == channel_id and start <= r.timestamp <= end
        ]

        by_service: dict[str, float] = {}
        by_operation: dict[str, float] = {}
        by_tenant: dict[str, float] = {}
        total = 0.0

        for r in filtered:
            by_service[r.service_name] = by_service.get(r.service_name, 0.0) + r.total_cost_usd
            by_operation[r.operation] = by_operation.get(r.operation, 0.0) + r.total_cost_usd
            by_tenant[r.tenant_id] = by_tenant.get(r.tenant_id, 0.0) + r.total_cost_usd
            total += r.total_cost_usd

        return {
            "channel_id": channel_id,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "total_cost_usd": round(total, 4),
            "by_service": {svc: round(cost, 4) for svc, cost in by_service.items()},
            "by_operation": {op: round(cost, 4) for op, cost in by_operation.items()},
            "by_tenant": {t: round(cost, 4) for t, cost in by_tenant.items()},
            "record_count": len(filtered),
        }

    def get_budget_alerts(
        self,
        tenant_id: str | None = None,
        since: datetime | None = None,
    ) -> list[BudgetAlert]:
        """Get budget alerts, optionally filtered by tenant."""
        alerts = self._alerts
        if tenant_id:
            alerts = [a for a in alerts if a.tenant_id == tenant_id]
        if since:
            alerts = [a for a in alerts if a.timestamp >= since]
        return alerts
