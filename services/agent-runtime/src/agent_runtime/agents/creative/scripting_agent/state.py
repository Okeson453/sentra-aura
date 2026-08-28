"""State machine for the Scripting Agent reflection loop."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field

from agent_runtime.durable_state import DurableAgentState


class ScriptingState(str, Enum):
    """Lifecycle states for a scripting task."""

    IDLE = "idle"
    DRAFTING = "drafting"
    CRITIQUING = "critiquing"
    REWRITING = "rewriting"
    SPONSORSHIP = "sponsorship_injection"
    COMPLETED = "completed"
    FAILED = "failed"


class ReflectionState(DurableAgentState):
    """Mutable state carried across Draft → Critique → Rewrite rounds.

    Composes DurableAgentState (checkpoint_id, cost_accrued_usd, tokens_consumed, errors).
    """

    phase: ScriptingState = ScriptingState.IDLE
    round: int = 0
    max_rounds: int = 1
    draft_script: dict[str, Any] | None = None
    critique: dict[str, Any] | None = None
    rewritten_script: dict[str, Any] | None = None
    provider_texts: list[str] = Field(default_factory=list)
    provider_usages: list[dict[str, Any]] = Field(default_factory=list)
    sponsorship_applied: bool = False

    def advance(self, phase: ScriptingState) -> None:
        self.phase = phase

    def record_provider(self, text: str, usage: dict[str, Any] | None = None) -> None:
        self.provider_texts.append(text)
        if usage:
            self.provider_usages.append(usage)
            self.record_cost(
                amount_usd=float(usage.get("estimated_cost_usd") or 0.0),
                tokens=int(usage.get("total_tokens") or 0),
            )
