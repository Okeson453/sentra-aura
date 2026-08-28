"""Shared durable execution fields for domain agent state (Architecture §10).

Compose into per-agent pydantic state models — does not replace domain phases.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DurableAgentState(BaseModel):
    """Checkpoint / cost / error fields required for fault-tolerant automation."""

    checkpoint_id: str | None = None
    cost_accrued_usd: float = 0.0
    tokens_consumed: int = 0
    errors: list[str] = Field(default_factory=list)

    def record_cost(self, amount_usd: float = 0.0, tokens: int = 0) -> None:
        self.cost_accrued_usd = float(self.cost_accrued_usd) + float(amount_usd or 0.0)
        self.tokens_consumed = int(self.tokens_consumed) + int(tokens or 0)

    def record_error(self, message: str) -> None:
        self.errors.append(message)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DurableAgentState:
        return cls.model_validate(data)
