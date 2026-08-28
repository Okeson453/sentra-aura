"""Unit tests for agent lifecycle state machine."""
from __future__ import annotations

import pytest

from agent_registry_service.lifecycle_state_machine import (
    LifecycleRecord,
    LifecycleState,
    LifecycleStateMachine,
    TransitionTrigger,
)


def test_draft_to_canary_requires_approval():
    fsm = LifecycleStateMachine()
    fsm.register("agent-1", "1.0.0")

    with pytest.raises(ValueError, match="requires approval"):
        fsm.transition("agent-1", "1.0.0", TransitionTrigger.SUBMIT)

    record = fsm.transition("agent-1", "1.0.0", TransitionTrigger.SUBMIT, approved_by="admin@sentraaura.com")
    assert record.state == LifecycleState.CANARY


def test_canary_to_staging_requires_eval():
    fsm = LifecycleStateMachine()
    fsm.register("agent-1", "1.0.0")
    fsm.transition("agent-1", "1.0.0", TransitionTrigger.SUBMIT, approved_by="admin")

    with pytest.raises(ValueError, match="eval_score"):
        fsm.transition("agent-1", "1.0.0", TransitionTrigger.EVAL_PASS)

    record = fsm.transition("agent-1", "1.0.0", TransitionTrigger.EVAL_PASS, eval_score=0.85)
    assert record.state == LifecycleState.STAGING


def test_canary_to_draft_on_eval_fail():
    fsm = LifecycleStateMachine()
    fsm.register("agent-1", "1.0.0")
    fsm.transition("agent-1", "1.0.0", TransitionTrigger.SUBMIT, approved_by="admin")

    record = fsm.transition("agent-1", "1.0.0", TransitionTrigger.EVAL_FAIL)
    assert record.state == LifecycleState.DRAFT


def test_staging_to_production_requires_approval():
    fsm = LifecycleStateMachine()
    fsm.register("agent-1", "1.0.0")
    fsm.transition("agent-1", "1.0.0", TransitionTrigger.SUBMIT, approved_by="admin")
    fsm.transition("agent-1", "1.0.0", TransitionTrigger.EVAL_PASS, eval_score=0.85)

    with pytest.raises(ValueError, match="requires approval"):
        fsm.transition("agent-1", "1.0.0", TransitionTrigger.PROMOTE)

    record = fsm.transition("agent-1", "1.0.0", TransitionTrigger.PROMOTE, approved_by="admin")
    assert record.state == LifecycleState.PRODUCTION


def test_invalid_transition():
    fsm = LifecycleStateMachine()
    fsm.register("agent-1", "1.0.0")

    with pytest.raises(ValueError, match="Invalid transition"):
        fsm.transition("agent-1", "1.0.0", TransitionTrigger.PROMOTE)


def test_history_tracking():
    fsm = LifecycleStateMachine()
    fsm.register("agent-1", "1.0.0")
    fsm.transition("agent-1", "1.0.0", TransitionTrigger.SUBMIT, approved_by="admin")
    record = fsm.get_record("agent-1", "1.0.0")
    assert len(record.history) == 1
    assert record.history[0]["from"] == "draft"
    assert record.history[0]["to"] == "canary"


def test_list_by_state():
    fsm = LifecycleStateMachine()
    fsm.register("agent-1", "1.0.0")
    fsm.register("agent-2", "1.0.0")
    fsm.transition("agent-1", "1.0.0", TransitionTrigger.SUBMIT, approved_by="admin")

    drafts = fsm.list_by_state(LifecycleState.DRAFT)
    canaries = fsm.list_by_state(LifecycleState.CANARY)
    assert len(drafts) == 1
    assert len(canaries) == 1
