"""Domain state for AI Clipping Agent (Arch. §6 pipeline phases)."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field

from agent_runtime.durable_state import DurableAgentState


class ClippingPhase(str, Enum):
    IDLE = "idle"
    INGESTING = "ingesting_segments"
    SEGMENTING = "semantic_segmentation"
    SCORING = "highlight_scoring"
    CONTEXT = "context_reconstruction"
    RANKING = "diversity_rank_select"
    COMPLETED = "completed"
    FAILED = "failed"


# Backward-compatible aliases used by older imports
AiClippingPhase = ClippingPhase


class ClippingState(DurableAgentState):
    phase: ClippingPhase = ClippingPhase.IDLE
    segment_count: int = 0
    candidate_count: int = 0
    selected_count: int = 0
    provider_texts: list[str] = Field(default_factory=list)
    provider_usages: list[dict[str, Any]] = Field(default_factory=list)

    def advance(self, phase: ClippingPhase) -> None:
        self.phase = phase

    def record_provider(self, text: str, usage: dict[str, Any] | None = None) -> None:
        self.provider_texts.append(text)
        if usage:
            self.provider_usages.append(usage)
            self.record_cost(
                amount_usd=float(usage.get("estimated_cost_usd") or 0.0),
                tokens=int(usage.get("total_tokens") or 0),
            )


AiClippingState = ClippingState
