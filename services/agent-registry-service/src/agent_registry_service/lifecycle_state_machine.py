"""Agent lifecycle state machine: DRAFT -> CANARY -> STAGING -> PRODUCTION -> DEPRECATED."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class LifecycleState(str, Enum):
    DRAFT = "draft"
    CANARY = "canary"
    STAGING = "staging"
    PRODUCTION = "production"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class TransitionTrigger(str, Enum):
    SUBMIT = "submit"
    EVAL_PASS = "eval_pass"
    EVAL_FAIL = "eval_fail"
    PROMOTE = "promote"
    ROLLBACK = "rollback"
    DEPRECATE = "deprecate"
    ARCHIVE = "archive"
    EMERGENCY_OVERRIDE = "emergency_override"


@dataclass
class LifecycleTransition:
    from_state: LifecycleState
    to_state: LifecycleState
    trigger: TransitionTrigger
    requires_approval: bool = False
    required_eval_score: float | None = None
    auto_promote: bool = False


# Valid transitions
VALID_TRANSITIONS: list[LifecycleTransition] = [
    LifecycleTransition(LifecycleState.DRAFT, LifecycleState.CANARY, TransitionTrigger.SUBMIT, requires_approval=True),
    LifecycleTransition(LifecycleState.CANARY, LifecycleState.STAGING, TransitionTrigger.EVAL_PASS, required_eval_score=0.80),
    LifecycleTransition(LifecycleState.CANARY, LifecycleState.DRAFT, TransitionTrigger.EVAL_FAIL),
    LifecycleTransition(LifecycleState.STAGING, LifecycleState.PRODUCTION, TransitionTrigger.PROMOTE, requires_approval=True),
    LifecycleTransition(LifecycleState.STAGING, LifecycleState.CANARY, TransitionTrigger.ROLLBACK),
    LifecycleTransition(LifecycleState.PRODUCTION, LifecycleState.DEPRECATED, TransitionTrigger.DEPRECATE),
    LifecycleTransition(LifecycleState.PRODUCTION, LifecycleState.STAGING, TransitionTrigger.ROLLBACK),
    LifecycleTransition(LifecycleState.DEPRECATED, LifecycleState.ARCHIVED, TransitionTrigger.ARCHIVE),
    LifecycleTransition(LifecycleState.DEPRECATED, LifecycleState.PRODUCTION, TransitionTrigger.EMERGENCY_OVERRIDE),
    # Emergency: any state -> DRAFT on eval failure
    LifecycleTransition(LifecycleState.STAGING, LifecycleState.DRAFT, TransitionTrigger.EVAL_FAIL),
    LifecycleTransition(LifecycleState.PRODUCTION, LifecycleState.DRAFT, TransitionTrigger.EVAL_FAIL),
]


@dataclass
class LifecycleRecord:
    agent_id: str
    version: str
    state: LifecycleState = LifecycleState.DRAFT
    history: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def transition(self, trigger: TransitionTrigger, eval_score: float | None = None, approved_by: str | None = None) -> LifecycleState:
        """Attempt a state transition."""
        for vt in VALID_TRANSITIONS:
            if vt.from_state == self.state and vt.trigger == trigger:
                if vt.required_eval_score is not None and (eval_score is None or eval_score < vt.required_eval_score):
                    raise ValueError(
                        f"Transition {trigger.value} requires eval_score >= {vt.required_eval_score}, got {eval_score}"
                    )
                if vt.requires_approval and not approved_by:
                    raise ValueError(f"Transition {trigger.value} from {self.state.value} requires approval")

                old_state = self.state
                self.state = vt.to_state
                self.updated_at = datetime.utcnow()
                self.history.append({
                    "from": old_state.value,
                    "to": vt.to_state.value,
                    "trigger": trigger.value,
                    "eval_score": eval_score,
                    "approved_by": approved_by,
                    "timestamp": self.updated_at.isoformat(),
                })
                return self.state

        raise ValueError(f"Invalid transition {trigger.value} from state {self.state.value}")

    def can_transition(self, trigger: TransitionTrigger) -> bool:
        """Check if a transition is valid from the current state."""
        return any(vt.from_state == self.state and vt.trigger == trigger for vt in VALID_TRANSITIONS)


class LifecycleStateMachine:
    """Manages lifecycle states for all registered agent versions."""

    def __init__(self) -> None:
        self._records: dict[str, LifecycleRecord] = {}  # key: agent_id:version

    def register(self, agent_id: str, version: str) -> LifecycleRecord:
        """Register a new agent version in DRAFT state."""
        key = f"{agent_id}:{version}"
        if key in self._records:
            raise ValueError(f"Agent version {key} already registered")
        record = LifecycleRecord(agent_id=agent_id, version=version)
        self._records[key] = record
        return record

    def transition(
        self,
        agent_id: str,
        version: str,
        trigger: TransitionTrigger,
        eval_score: float | None = None,
        approved_by: str | None = None,
    ) -> LifecycleRecord:
        """Execute a lifecycle transition."""
        key = f"{agent_id}:{version}"
        record = self._records.get(key)
        if not record:
            raise ValueError(f"Agent version {key} not found")
        record.transition(trigger, eval_score=eval_score, approved_by=approved_by)
        return record

    def get_state(self, agent_id: str, version: str) -> LifecycleState:
        key = f"{agent_id}:{version}"
        record = self._records.get(key)
        if not record:
            raise ValueError(f"Agent version {key} not found")
        return record.state

    def get_record(self, agent_id: str, version: str) -> LifecycleRecord:
        key = f"{agent_id}:{version}"
        record = self._records.get(key)
        if not record:
            raise ValueError(f"Agent version {key} not found")
        return record

    def list_by_state(self, state: LifecycleState) -> list[LifecycleRecord]:
        return [r for r in self._records.values() if r.state == state]
