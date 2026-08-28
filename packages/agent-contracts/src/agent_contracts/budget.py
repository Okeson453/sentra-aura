"""Cost budget contract for SentraAura agents.

Matches Architecture §4.1 and §17.4.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class BudgetStatus(str, Enum):
    ACTIVE = "ACTIVE"
    EXHAUSTED = "EXHAUSTED"
    PAUSED = "PAUSED"
    OVERRIDDEN = "OVERRIDDEN"


@dataclass
class CostBudget:
    """Budget allocation for an agent task."""

    total_budget_usd: float = 0.0
    spent_usd: float = 0.0
    remaining_usd: float = 0.0
    currency: str = "USD"
    status: BudgetStatus = BudgetStatus.ACTIVE
    cost_center: str = ""
    channel_id: str | None = None
    alerts: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.remaining_usd == 0.0 and self.total_budget_usd > 0.0:
            self.remaining_usd = self.total_budget_usd - self.spent_usd

    def spend(self, amount: float) -> None:
        """Record a spend against this budget."""
        self.spent_usd += amount
        self.remaining_usd = max(0.0, self.total_budget_usd - self.spent_usd)
        if self.remaining_usd <= 0.0:
            self.status = BudgetStatus.EXHAUSTED

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_budget_usd": self.total_budget_usd,
            "spent_usd": self.spent_usd,
            "remaining_usd": self.remaining_usd,
            "currency": self.currency,
            "status": self.status.value,
            "cost_center": self.cost_center,
            "channel_id": self.channel_id,
            "alerts": self.alerts,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CostBudget":
        return cls(
            total_budget_usd=data.get("total_budget_usd", 0.0),
            spent_usd=data.get("spent_usd", 0.0),
            remaining_usd=data.get("remaining_usd", 0.0),
            currency=data.get("currency", "USD"),
            status=BudgetStatus(data.get("status", "ACTIVE")),
            cost_center=data.get("cost_center", ""),
            channel_id=data.get("channel_id"),
            alerts=data.get("alerts", []),
            metadata=data.get("metadata", {}),
        )
