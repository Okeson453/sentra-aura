"""Tests for Portfolio Strategy Agent against mock-provider-gateway."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from agent_contracts.envelope import AgentMessage
from agent_runtime.agents.intelligence.portfolio_strategy_agent.agent import (
    PortfolioStrategyAgent,
)
from agent_runtime.agents.intelligence.portfolio_strategy_agent.config import (
    PortfolioStrategyConfig,
)
from agent_runtime.agents.intelligence.executive_orchestrator_agent.agent import (
    ExecutiveOrchestratorAgent,
)
from agent_runtime.agents.intelligence.executive_orchestrator_agent.config import (
    ExecutiveOrchestratorConfig,
)
from agent_runtime.envelope import AgentMessageEnvelope

REPO_ROOT = Path(__file__).resolve().parents[8]
MOCK_MAIN = REPO_ROOT / "local" / "mock-provider-gateway" / "main.py"
MOCK_PORT = int(os.environ.get("PSA_TEST_GATEWAY_PORT", "18085"))
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
    return PortfolioStrategyAgent(
        config=PortfolioStrategyConfig(
            provider_gateway_url=mock_gateway,
            timeout_seconds=30.0,
        )
    )


def _env(payload: dict, task_type: str = "plan") -> AgentMessageEnvelope:
    msg = AgentMessage(
        agent_type="portfolio_strategy_agent",
        task_type=task_type,
        payload={**payload, "task_type": task_type},
    )
    return AgentMessageEnvelope(message=msg)


class TestPortfolioStrategyAgent:
    def test_capabilities(self, agent):
        assert "analyze_portfolio" in agent.capabilities
        assert "budget_allocation" in agent.capabilities

    def test_identity(self, agent):
        assert agent.agent_id == "portfolio_strategy_agent"
        assert agent.domain == "intelligence"

    @pytest.mark.asyncio
    async def test_uses_provider_not_stub(self, agent):
        result = await agent.run(
            _env(
                {
                    "portfolio_name": "Growth Portfolio",
                    "total_budget_usd": 2500.0,
                    "channels": [{"channel_id": "alpha"}, {"channel_id": "beta"}],
                    "content_themes": ["tutorials", "reviews"],
                    "planning_period_days": 30,
                    "risk_tolerance": "medium",
                }
            )
        )
        assert result["raw_provider_text"]
        assert result["topic_quotas"]
        assert result["budget_allocation"]
        assert result["portfolio_plan"]
        blob = str(result)
        # Old synthetic calendar themes must not be forced
        assert "Schedule slippage: buffer 20%" not in blob
        assert "Content fatigue: rotate themes every 2 weeks" not in blob or result["raw_provider_text"]

    @pytest.mark.asyncio
    async def test_output_varies_with_input(self, agent):
        r1 = await agent.run(
            _env(
                {
                    "portfolio_name": "Alpha Fund",
                    "total_budget_usd": 500.0,
                    "channels": [{"channel_id": "a1"}],
                    "content_themes": ["science"],
                    "max_videos_per_week": 2,
                }
            )
        )
        r2 = await agent.run(
            _env(
                {
                    "portfolio_name": "Beta Fund",
                    "total_budget_usd": 8000.0,
                    "channels": [{"channel_id": "b1"}, {"channel_id": "b2"}, {"channel_id": "b3"}],
                    "content_themes": ["comedy", "gaming"],
                    "max_videos_per_week": 6,
                }
            )
        )
        assert r1["portfolio_plan_summary"] != r2["portfolio_plan_summary"] or r1["raw_provider_text"] != r2["raw_provider_text"]
        assert r2["emphasize_distribution"] is True
        assert r1["emphasize_distribution"] is False

    @pytest.mark.asyncio
    async def test_orchestrator_consumes_portfolio_plan(self, agent, mock_gateway):
        """Dispatch shape: PSA output → executive_orchestrator as portfolio_plan payload."""
        psa = await agent.run(
            _env(
                {
                    "portfolio_name": "Chain Portfolio",
                    "total_budget_usd": 3000.0,
                    "channels": [{"channel_id": "c1"}, {"channel_id": "c2"}],
                    "content_themes": ["education"],
                    "max_videos_per_week": 6,
                }
            )
        )
        plan = psa["portfolio_plan"]
        assert "topic_quotas" in plan
        assert "budget_allocation" in plan
        assert plan.get("emphasize_distribution") is True

        orch = ExecutiveOrchestratorAgent(
            config=ExecutiveOrchestratorConfig(
                provider_gateway_url=mock_gateway,
                timeout_seconds=30.0,
            )
        )
        orch_env = AgentMessageEnvelope(
            message=AgentMessage(
                agent_type="executive_orchestrator_agent",
                task_type="strategy",
                payload={
                    "channel_name": "ChainChannel",
                    "portfolio_name": "Chain Portfolio",
                    "budget_remaining": 3000.0,
                    "max_videos_per_week": 6,
                    "portfolio_plan": plan,
                    "market_intelligence": {
                        "top_topics": [{"topic": "education tools"}],
                        "opportunity_score": 80,
                    },
                    "trend_signals": [{"topic": "education tools", "velocity": 0.9}],
                },
            )
        )
        orch_result = await orch.run(orch_env)
        notes = " ".join(orch_result.get("coordination_notes") or [])
        assert "portfolio_plan" in notes
        agent_ids = {a["agent_id"] for a in orch_result["agent_assignments"]}
        assert "publishing_agent" in agent_ids  # emphasize_distribution from PSA
        assert "portfolio_strategy_agent" in agent_ids
        assert orch_result["raw_provider_text"]


class TestSchemas:
    def test_request_defaults(self):
        from agent_runtime.agents.intelligence.portfolio_strategy_agent.schemas import (
            PortfolioPlanRequest,
        )

        r = PortfolioPlanRequest()
        assert r.total_budget_usd == 1000.0
        assert r.planning_period_days == 30


class TestPermissionEnforcement:
    @pytest.mark.asyncio
    async def test_revoke_denies_primary_tool(self, mock_gateway):
        from agent_runtime.tool_permissions import PermissionDeniedError, PermissionMatrix
        matrix = PermissionMatrix()
        for tool in ["analyze_portfolio"]:
            matrix.revoke("portfolio_strategy_agent", tool, "execute")
        from agent_runtime.agents.intelligence.portfolio_strategy_agent.agent import PortfolioStrategyAgent
        from agent_runtime.agents.intelligence.portfolio_strategy_agent.config import PortfolioStrategyConfig
        agent = PortfolioStrategyAgent(
            config=PortfolioStrategyConfig(provider_gateway_url=mock_gateway),
            permission_matrix=matrix,
        )
        with pytest.raises(PermissionDeniedError):
            await agent.run(_env({"channel_name": "Deny"}))

    @pytest.mark.asyncio
    async def test_never_listed_tool_default_deny(self, agent):
        from agent_runtime.tool_permissions import PermissionDeniedError
        name = "never_listed_tool_zz_ps"
        perm = agent.permissions.matrix.check(agent.agent_id, name, "execute")
        assert perm.decision.value == "deny"
        assert "No permission rule defined" in perm.justification
        async def _dummy() -> str:
            return "nope"
        agent.register_tool(name, _dummy)
        with pytest.raises(PermissionDeniedError) as ei:
            await agent.invoke_tool(name)
        assert "No permission rule defined" in str(ei.value) or "default deny" in str(ei.value).lower()
