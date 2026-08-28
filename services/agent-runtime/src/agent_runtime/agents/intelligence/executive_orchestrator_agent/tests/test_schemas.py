"""Schema tests for Executive Orchestrator."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent_runtime.agents.intelligence.executive_orchestrator_agent.schemas import (
    StrategyRequest,
    StrategyResponse,
)


def test_request_defaults():
    req = StrategyRequest(channel_name="Ch")
    assert req.max_videos_per_week == 3
    assert req.task_type == "strategy"


def test_response_requires_summary():
    with pytest.raises(ValidationError):
        StrategyResponse()  # strategy_summary required


def test_response_roundtrip():
    r = StrategyResponse(
        strategy_summary="s",
        content_pillars=["a"],
        agent_assignments=[{"agent_id": "research_agent", "swarm": "creative", "task": "x"}],
        workflow_dag=[{"node_id": "n1", "agent_id": "research_agent", "description": "x"}],
    )
    assert StrategyResponse(**r.model_dump()).strategy_summary == "s"
