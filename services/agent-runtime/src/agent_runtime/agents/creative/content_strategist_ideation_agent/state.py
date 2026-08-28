from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import Field
from agent_runtime.durable_state import DurableAgentState

class CSIPhase(str, Enum):
    IDLE = "idle"
    GENERATING = "generating"
    SCORING = "scoring"
    COMPLETED = "completed"
    FAILED = "failed"

class CSIState(DurableAgentState):
    phase: CSIPhase = CSIPhase.IDLE
    provider_texts: list[str] = Field(default_factory=list)
    provider_usages: list[dict[str, Any]] = Field(default_factory=list)

    def advance(self, phase: CSIPhase) -> None:
        self.phase = phase

    def record_provider(self, text: str, usage: dict[str, Any] | None = None) -> None:
        self.provider_texts.append(text)
        if usage:
            self.provider_usages.append(usage)
            self.record_cost(
                amount_usd=float(usage.get("estimated_cost_usd") or 0.0),
                tokens=int(usage.get("total_tokens") or 0),
            )
