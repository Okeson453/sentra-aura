"""Domain phase state for visual_asset_agent composed with DurableAgentState."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field

from agent_runtime.durable_state import DurableAgentState


class VAPhase(str, Enum):
    IDLE = "idle"
    GENERATING = "generating"
    EDITING = "editing"
    COMPLETED = "completed"
    FAILED = "failed"


class VAState(DurableAgentState):
    phase: VAPhase = VAPhase.IDLE
    generated: list[dict[str, Any]] = Field(default_factory=list)
    prompts_used: list[str] = Field(default_factory=list)

    def advance(self, phase: VAPhase) -> None:
        self.phase = phase
