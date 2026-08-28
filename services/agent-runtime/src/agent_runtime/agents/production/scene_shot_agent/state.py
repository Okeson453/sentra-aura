from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import Field
from agent_runtime.durable_state import DurableAgentState

class ShotPlanPhase(str, Enum):
    IDLE = "idle"
    INGESTING = "ingesting_script_assets"
    PLANNING = "planning_shots"
    EDL = "building_edl"
    COMPLETED = "completed"
    FAILED = "failed"

class ShotPlanState(DurableAgentState):
    phase: ShotPlanPhase = ShotPlanPhase.IDLE
    provider_texts: list[str] = Field(default_factory=list)
    provider_usages: list[dict[str, Any]] = Field(default_factory=list)
    shot_count: int = 0

    def advance(self, phase: ShotPlanPhase) -> None:
        self.phase = phase

    def record_provider(self, text: str, usage: dict[str, Any] | None = None) -> None:
        self.provider_texts.append(text)
        if usage:
            self.provider_usages.append(usage)
            self.record_cost(
                amount_usd=float(usage.get("estimated_cost_usd") or 0.0),
                tokens=int(usage.get("total_tokens") or 0),
            )
