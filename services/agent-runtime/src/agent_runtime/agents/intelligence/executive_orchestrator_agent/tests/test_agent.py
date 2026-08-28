"""Tests for Executive Orchestrator against local mock-provider-gateway."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from agent_contracts.envelope import AgentMessage
from agent_runtime.agents.intelligence.executive_orchestrator_agent.agent import (
    ExecutiveOrchestratorAgent,
)
from agent_runtime.agents.intelligence.executive_orchestrator_agent.config import (
    ExecutiveOrchestratorConfig,
)
from agent_runtime.envelope import AgentMessageEnvelope

REPO_ROOT = Path(__file__).resolve().parents[8]
MOCK_MAIN = REPO_ROOT / "local" / "mock-provider-gateway" / "main.py"
MOCK_PORT = int(os.environ.get("EXEC_ORCH_TEST_GATEWAY_PORT", "18082"))
MOCK_URL = f"http://127.0.0.1:{MOCK_PORT}"


@pytest.fixture(scope="module")
def mock_gateway():
    if not MOCK_MAIN.exists():
        pytest.skip(f"mock gateway not found at {MOCK_MAIN}")
    env = {**os.environ, "PORT": str(MOCK_PORT)}
    proc = subprocess.Popen(
        [sys.executable, str(MOCK_MAIN)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    deadline = time.time() + 15
    ready = False
    while time.time() < deadline:
        try:
            if httpx.get(f"{MOCK_URL}/health", timeout=1.0).status_code == 200:
                ready = True
                break
        except Exception:
            time.sleep(0.2)
    if not ready:
        proc.terminate()
        out, err = proc.communicate(timeout=5)
        pytest.fail(f"mock gateway failed: {err.decode() or out.decode()}")
    yield MOCK_URL
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture
def agent(mock_gateway):
    return ExecutiveOrchestratorAgent(
        config=ExecutiveOrchestratorConfig(
            provider_gateway_url=mock_gateway,
            timeout_seconds=30.0,
        )
    )


def _env(payload: dict) -> AgentMessageEnvelope:
    msg = AgentMessage(
        agent_type="executive_orchestrator_agent",
        task_type="strategy",
        payload={**payload, "task_type": "strategy"},
    )
    return AgentMessageEnvelope(message=msg)


class TestExecutiveOrchestratorAgent:
    def test_capabilities(self, agent):
        assert "strategy" in agent.capabilities
        assert "orchestration" in agent.capabilities
        assert "inter_swarm_workflow" in agent.capabilities

    def test_agent_identity(self, agent):
        assert agent.agent_id == "executive_orchestrator_agent"
        assert agent.domain == "intelligence"

    @pytest.mark.asyncio
    async def test_execute_uses_provider(self, agent, mock_gateway):
        result = await agent.run(
            _env(
                {
                    "channel_name": "TestChannel",
                    "portfolio_name": "Test Portfolio",
                    "budget_remaining": 500.0,
                    "planning_horizon": "30 days",
                    "max_videos_per_week": 4,
                }
            )
        )
        assert "strategy_summary" in result
        assert result["raw_provider_text"]
        assert "synthetic" not in (result.get("strategy_summary") or "").lower()
        assert result["agent_assignments"]
        assert result["workflow_dag"]
        # No hardcoded stub schedule week labels required

    @pytest.mark.asyncio
    async def test_output_varies_with_input(self, agent, mock_gateway):
        r1 = await agent.run(
            _env(
                {
                    "channel_name": "AlphaChannel",
                    "trend_signals": [{"topic": "Quantum Cooking", "velocity": 0.9}],
                    "max_videos_per_week": 2,
                }
            )
        )
        r2 = await agent.run(
            _env(
                {
                    "channel_name": "BetaChannel",
                    "trend_signals": [{"topic": "Space Carpentry", "velocity": 0.8}],
                    "max_videos_per_week": 6,
                    "portfolio_plan": {"emphasize_distribution": True},
                }
            )
        )
        assert r1["strategy_summary"] != r2["strategy_summary"] or r1["raw_provider_text"] != r2["raw_provider_text"]
        assert "AlphaChannel" in r1["strategy_summary"] or "AlphaChannel" in (r1["raw_provider_text"] or "")
        # Beta with emphasize_distribution should get publishing_agent assignment
        beta_agents = {a["agent_id"] for a in r2["agent_assignments"]}
        assert "publishing_agent" in beta_agents
        alpha_agents = {a["agent_id"] for a in r1["agent_assignments"]}
        assert "publishing_agent" not in alpha_agents

    @pytest.mark.asyncio
    async def test_coordinates_peer_intelligence_inputs(self, agent, mock_gateway):
        result = await agent.run(
            _env(
                {
                    "channel_name": "IntelChannel",
                    "market_intelligence": {
                        "top_topics": [{"topic": "Edge AI"}],
                        "opportunity_score": 88,
                    },
                    "portfolio_plan": {
                        "topic_quotas": {"tutorials": 2},
                        "budget_allocation": {"production": 0.4},
                    },
                    "trend_signals": [{"topic": "Edge AI", "velocity": 0.95}],
                }
            )
        )
        notes = " ".join(result.get("coordination_notes") or [])
        assert "portfolio_plan" in notes
        assert "market" in notes.lower() or "trend" in notes.lower()
        agent_ids = [a["agent_id"] for a in result["agent_assignments"]]
        assert "market_audience_intelligence_agent" in agent_ids
        assert "portfolio_strategy_agent" in agent_ids
        assert "research_agent" in agent_ids


class TestPermissionEnforcement:
    @pytest.mark.asyncio
    async def test_revoke_denies_plan_workflow(self, mock_gateway):
        from agent_runtime.tool_permissions import PermissionDeniedError, PermissionMatrix

        matrix = PermissionMatrix()
        matrix.revoke("executive_orchestrator_agent", "plan_workflow", "execute")
        matrix.revoke("executive_orchestrator_agent", "dispatch_task", "execute")
        from agent_runtime.agents.intelligence.executive_orchestrator_agent.config import (
            ExecutiveOrchestratorConfig,
        )
        from agent_runtime.agents.intelligence.executive_orchestrator_agent.agent import (
            ExecutiveOrchestratorAgent,
        )

        agent = ExecutiveOrchestratorAgent(
            config=ExecutiveOrchestratorConfig(provider_gateway_url=mock_gateway),
            permission_matrix=matrix,
        )
        with pytest.raises(PermissionDeniedError):
            await agent.run(_env({"channel_name": "DenyProbe"}))

    @pytest.mark.asyncio
    async def test_never_listed_tool_default_deny(self, agent):
        from agent_runtime.tool_permissions import PermissionDeniedError

        name = "never_listed_exec_tool_zz9"
        perm = agent.permissions.matrix.check(agent.agent_id, name, "execute")
        assert perm.decision.value == "deny"
        assert "No permission rule defined" in perm.justification

        async def _dummy() -> str:
            return "nope"

        agent.register_tool(name, _dummy)
        with pytest.raises(PermissionDeniedError) as ei:
            await agent.invoke_tool(name)
        assert "No permission rule defined" in str(ei.value) or "default deny" in str(ei.value).lower()


class TestEscalationConditions:
    """Escalations evaluated against structured orchestrator/workflow state."""

    @pytest.mark.asyncio
    async def test_workflow_stuck_escalation(self, agent, mock_gateway):
        from datetime import datetime, timedelta, timezone

        stuck_since = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        result = await agent.run(
            _env(
                {
                    "channel_name": "EscChannel",
                    "workflow_state": {
                        "active_workflows": [
                            {
                                "id": "wf-stuck-1",
                                "status": "running",
                                "last_progress_at": stuck_since,
                            }
                        ]
                    },
                }
            )
        )
        conditions = [e["condition"] for e in result.get("escalations") or []]
        assert "workflow_stuck" in conditions

    @pytest.mark.asyncio
    async def test_resource_exhaustion_escalation(self, agent, mock_gateway):
        result = await agent.run(
            _env(
                {
                    "channel_name": "ResChannel",
                    "resource_metrics": {
                        "cpu_utilization": 0.92,
                        "memory_utilization": 0.88,
                        "exhaustion_window_hours": 1.5,
                    },
                }
            )
        )
        conditions = [e["condition"] for e in result.get("escalations") or []]
        assert "resource_exhaustion" in conditions

    @pytest.mark.asyncio
    async def test_budget_overrun_escalation(self, agent, mock_gateway):
        result = await agent.run(
            _env(
                {
                    "channel_name": "BudChannel",
                    "budget_metrics": {"allocated_usd": 1000.0, "spent_usd": 1200.0},
                }
            )
        )
        conditions = [e["condition"] for e in result.get("escalations") or []]
        assert "budget_overrun" in conditions

    @pytest.mark.asyncio
    async def test_consecutive_failures_escalation(self, agent, mock_gateway):
        history = [{"status": "failed", "error": f"e{i}"} for i in range(5)]
        result = await agent.run(
            _env({"channel_name": "FailChannel", "failure_history": history})
        )
        conditions = [e["condition"] for e in result.get("escalations") or []]
        assert "consecutive_failures" in conditions

    @pytest.mark.asyncio
    async def test_no_false_escalation_when_healthy(self, agent, mock_gateway):
        from datetime import datetime, timezone

        result = await agent.run(
            _env(
                {
                    "channel_name": "Healthy",
                    "workflow_state": {
                        "active_workflows": [
                            {
                                "id": "wf-ok",
                                "status": "running",
                                "last_progress_at": datetime.now(timezone.utc).isoformat(),
                            }
                        ]
                    },
                    "resource_metrics": {
                        "cpu_utilization": 0.4,
                        "memory_utilization": 0.3,
                        "exhaustion_window_hours": 2.0,
                    },
                    "budget_metrics": {"allocated_usd": 1000.0, "spent_usd": 500.0},
                    "failure_history": [{"status": "ok"}],
                }
            )
        )
        assert result.get("escalations") == []
