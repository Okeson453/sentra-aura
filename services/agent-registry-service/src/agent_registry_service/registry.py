"""High-level registry operations combining store + lifecycle."""
from __future__ import annotations

import logging
from typing import Any

from agent_registry_service.lifecycle_state_machine import LifecycleStateMachine, LifecycleState, TransitionTrigger
from agent_registry_service.models import AgentRegistration, AgentStatus, EvaluationRecord, EvaluationStatus, RegisteredAgent
from agent_registry_service.store import AgentStore

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Unified agent registry with lifecycle management."""

    def __init__(self, store: AgentStore | None = None) -> None:
        self.store = store or AgentStore()
        self.lifecycle = LifecycleStateMachine()

    def register(self, registration: AgentRegistration) -> RegisteredAgent:
        """Register a new agent and initialize its lifecycle."""
        registered = self.store.register(registration)
        self.lifecycle.register(registration.agent_id, registration.version)
        logger.info("Registered agent %s v%s in lifecycle DRAFT", registration.agent_id, registration.version)
        return registered

    def promote(
        self,
        agent_id: str,
        version: str,
        trigger: TransitionTrigger,
        eval_score: float | None = None,
        approved_by: str | None = None,
    ) -> dict[str, Any]:
        """Promote an agent version through its lifecycle."""
        record = self.lifecycle.transition(agent_id, version, trigger, eval_score=eval_score, approved_by=approved_by)

        # Sync store status with lifecycle state
        agent = self.store.get(agent_id)
        if agent:
            state_to_status = {
                LifecycleState.DRAFT: AgentStatus.EXPERIMENTAL,
                LifecycleState.CANARY: AgentStatus.ACTIVE,
                LifecycleState.STAGING: AgentStatus.ACTIVE,
                LifecycleState.PRODUCTION: AgentStatus.ACTIVE,
                LifecycleState.DEPRECATED: AgentStatus.DEPRECATED,
                LifecycleState.ARCHIVED: AgentStatus.DISABLED,
            }
            new_status = state_to_status.get(record.state, AgentStatus.ACTIVE)
            # Update via store's update mechanism
            reg = self.store._agents.get(agent_id)
            if reg:
                reg.status = new_status
                reg.updated_at = record.updated_at

        return {
            "agent_id": agent_id,
            "version": version,
            "state": record.state.value,
            "history": record.history,
        }

    def evaluate(self, agent_id: str, record: EvaluationRecord) -> EvaluationRecord:
        """Submit an evaluation and auto-promote if criteria met."""
        result = self.store.add_evaluation(record)

        # Auto-promote CANARY -> STAGING on high score
        if record.status == EvaluationStatus.CANARY and record.score >= 0.80:
            try:
                self.promote(
                    agent_id,
                    record.version or "1.0.0",
                    TransitionTrigger.EVAL_PASS,
                    eval_score=record.score,
                )
            except ValueError as exc:
                logger.warning("Auto-promote failed for %s: %s", agent_id, exc)

        return result

    def get_full_record(self, agent_id: str) -> dict[str, Any]:
        """Get combined registry + lifecycle data for an agent."""
        agent = self.store.get(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        versions = self.store.list_versions(agent_id)
        lifecycle_states = {}
        for v in versions:
            try:
                lifecycle_states[v.version] = self.lifecycle.get_state(agent_id, v.version).value
            except ValueError:
                lifecycle_states[v.version] = "unknown"

        return {
            "agent": agent.model_dump(),
            "versions": [v.model_dump() for v in versions],
            "evaluations": [e.model_dump() for e in self.store.get_evaluations(agent_id)],
            "lifecycle_states": lifecycle_states,
        }
