"""Unit tests for unified agent registry."""
from __future__ import annotations

import pytest

from agent_registry_service.models import AgentRegistration, AgentType
from agent_registry_service.registry import AgentRegistry
from agent_registry_service.store import AgentStore
from agent_registry_service.lifecycle_state_machine import TransitionTrigger


def test_register_agent():
    store = AgentStore()
    registry = AgentRegistry(store)
    reg = AgentRegistration(
        agent_id="test-agent",
        name="Test Agent",
        domain="creative",
        agent_type=AgentType.SCRIPT_WRITER,
        version="1.0.0",
        description="A test agent",
        capabilities=["scripting"],
    )
    result = registry.register(reg)
    assert result.agent_id == "test-agent"
    assert result.version == "1.0.0"


def test_promote_with_eval():
    store = AgentStore()
    registry = AgentRegistry(store)
    reg = AgentRegistration(
        agent_id="test-agent",
        name="Test Agent",
        domain="creative",
        agent_type=AgentType.SCRIPT_WRITER,
        version="1.0.0",
    )
    registry.register(reg)

    # Submit to CANARY
    registry.promote("test-agent", "1.0.0", TransitionTrigger.SUBMIT, approved_by="admin")
    # Pass eval to STAGING
    result = registry.promote("test-agent", "1.0.0", TransitionTrigger.EVAL_PASS, eval_score=0.85)
    assert result["state"] == "staging"
