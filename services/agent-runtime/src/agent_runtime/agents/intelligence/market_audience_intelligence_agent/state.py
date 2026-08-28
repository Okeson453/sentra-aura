from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import Field
from agent_runtime.durable_state import DurableAgentState

class MAIPhase(str, Enum):
    IDLE = "idle"
    FETCHING = "fetching_ingestion"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"

class MAIState(DurableAgentState):
    phase: MAIPhase = MAIPhase.IDLE
    ingestion_jobs: list[dict[str, Any]] = Field(default_factory=list)
    provider_texts: list[str] = Field(default_factory=list)
    provider_usages: list[dict[str, Any]] = Field(default_factory=list)

    def advance(self, phase: MAIPhase) -> None:
        self.phase = phase

    def record_provider(self, text: str, usage: dict[str, Any] | None = None) -> None:
        self.provider_texts.append(text)
        if usage:
            self.provider_usages.append(usage)
            self.record_cost(
                amount_usd=float(usage.get("estimated_cost_usd") or 0.0),
                tokens=int(usage.get("total_tokens") or 0),
            )
