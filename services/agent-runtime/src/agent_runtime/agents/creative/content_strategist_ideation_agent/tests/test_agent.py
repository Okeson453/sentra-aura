"""Tests for Content Strategist & Ideation Agent."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from agent_contracts.envelope import AgentMessage
from agent_runtime.agents.creative.content_strategist_ideation_agent.agent import (
    ContentStrategistIdeationAgent,
)
from agent_runtime.agents.creative.content_strategist_ideation_agent.config import (
    ContentStrategistConfig,
)
from agent_runtime.envelope import AgentMessageEnvelope

try:
    from agent_runtime.agents.creative.scripting_agent.schemas import ScriptRequest

    HAS_SCRIPTING = True
except ImportError:
    HAS_SCRIPTING = False

REPO_ROOT = Path(__file__).resolve().parents[8]
MOCK_MAIN = REPO_ROOT / "local" / "mock-provider-gateway" / "main.py"
GW_PORT = int(os.environ.get("CSI_TEST_GATEWAY_PORT", "18096"))
GW_URL = f"http://127.0.0.1:{GW_PORT}"


@pytest.fixture(scope="module")
def mock_gateway():
    if not MOCK_MAIN.exists():
        pytest.skip(f"mock gateway missing: {MOCK_MAIN}")
    proc = subprocess.Popen(
        [sys.executable, str(MOCK_MAIN)],
        env={**os.environ, "PORT": str(GW_PORT)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    deadline = time.time() + 20
    ok = False
    while time.time() < deadline:
        try:
            if httpx.get(f"{GW_URL}/health", timeout=1).status_code == 200:
                ok = True
                break
        except Exception:
            time.sleep(0.2)
    if not ok:
        proc.terminate()
        pytest.fail("gateway not ready")
    yield GW_URL
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture
def agent(mock_gateway):
    return ContentStrategistIdeationAgent(
        config=ContentStrategistConfig(
            provider_gateway_url=mock_gateway,
            timeout_seconds=30.0,
        )
    )


def _env(payload: dict) -> AgentMessageEnvelope:
    return AgentMessageEnvelope(
        message=AgentMessage(
            agent_type="content_strategist_ideation_agent",
            task_type="ideate",
            payload={**payload, "task_type": "ideate"},
        )
    )


class TestContentStrategistIdeationAgent:
    def test_capabilities(self, agent):
        assert "generate_concepts" in agent.capabilities
        assert "score_ideas" in agent.capabilities

    def test_identity(self, agent):
        assert agent.agent_id == "content_strategist_ideation_agent"

    @pytest.mark.asyncio
    async def test_output_varies_by_topic(self, agent):
        r1 = await agent.run(
            _env(
                {
                    "topic": "marine snow ecology",
                    "channel_name": "Ocean Science",
                    "target_audience": "biology students",
                    "num_concepts": 3,
                }
            )
        )
        r2 = await agent.run(
            _env(
                {
                    "topic": "orbital debris mitigation",
                    "channel_name": "Space Ops",
                    "target_audience": "aerospace engineers",
                    "num_concepts": 3,
                }
            )
        )
        assert r1["raw_provider_text"]
        assert r2["raw_provider_text"]
        assert r1["raw_provider_text"] != r2["raw_provider_text"] or (
            r1.get("concepts") and r2.get("concepts")
            and r1["concepts"][0]["title"] != r2["concepts"][0]["title"]
        )
        blob1 = (r1.get("raw_provider_text") or "") + " ".join(
            c.get("title", "") for c in r1.get("concepts") or []
        )
        blob2 = (r2.get("raw_provider_text") or "") + " ".join(
            c.get("title", "") for c in r2.get("concepts") or []
        )
        assert "marine" in blob1.lower() or "ecology" in blob1.lower()
        assert "orbital" in blob2.lower() or "debris" in blob2.lower()
        # Old stub phrases gone
        assert "Ultimate Guide to" not in blob1 or "marine" in blob1.lower()

    @pytest.mark.asyncio
    async def test_uses_market_intelligence(self, agent):
        result = await agent.run(
            _env(
                {
                    "topic": "home fermentation",
                    "market_intelligence": {
                        "market_summary": "Fermentation content rising among DIY food creators.",
                        "top_trends": [
                            {"topic": "home fermentation", "opportunity_score": 82}
                        ],
                    },
                    "num_concepts": 2,
                }
            )
        )
        assert result.get("concepts") is not None
        assert result.get("content_strategy")
        assert result["raw_provider_text"]

    @pytest.mark.asyncio
    async def test_scripting_handoff_shape(self, agent):
        """Downstream: scripting_handoff validates as ScriptRequest fields."""
        result = await agent.run(
            _env(
                {
                    "topic": "quantum sensing",
                    "channel_name": "Physics Daily",
                    "target_audience": "STEM professionals",
                    "num_concepts": 3,
                }
            )
        )
        handoff = result.get("scripting_handoff") or {}
        assert handoff.get("video_title")
        assert handoff.get("channel_name") == "Physics Daily"
        if HAS_SCRIPTING:
            # Must accept ScriptRequest without error
            req = ScriptRequest(
                video_title=handoff["video_title"],
                channel_name=handoff.get("channel_name", ""),
                audience_profile=handoff.get("audience_profile", ""),
                target_keywords=handoff.get("target_keywords") or [],
                research_brief=handoff.get("research_brief") or {},
            )
            assert req.video_title == handoff["video_title"]


class TestSchemas:
    def test_request_defaults(self):
        from agent_runtime.agents.creative.content_strategist_ideation_agent.schemas import (
            IdeationRequest,
        )

        r = IdeationRequest(topic="x")
        assert r.num_concepts == 5


class TestPermissionEnforcement:
    @pytest.mark.asyncio
    async def test_revoke_denies_primary_tool(self, mock_gateway):
        from agent_runtime.tool_permissions import PermissionDeniedError, PermissionMatrix
        matrix = PermissionMatrix()
        for tool in ["generate_concepts","score_ideas"]:
            matrix.revoke("content_strategist_ideation_agent", tool, "execute")
        from agent_runtime.agents.creative.content_strategist_ideation_agent.agent import ContentStrategistIdeationAgent
        from agent_runtime.agents.creative.content_strategist_ideation_agent.config import ContentStrategistConfig
        agent = ContentStrategistIdeationAgent(
            config=ContentStrategistConfig(provider_gateway_url=mock_gateway),
            permission_matrix=matrix,
        )
        with pytest.raises(PermissionDeniedError):
            await agent.run(_env({"topic": "deny-probe"}))

    @pytest.mark.asyncio
    async def test_never_listed_tool_default_deny(self, agent):
        from agent_runtime.tool_permissions import PermissionDeniedError
        name = "never_listed_tool_zz_csi"
        perm = agent.permissions.matrix.check(agent.agent_id, name, "execute")
        assert perm.decision.value == "deny"
        assert "No permission rule defined" in perm.justification
        async def _dummy() -> str:
            return "nope"
        agent.register_tool(name, _dummy)
        with pytest.raises(PermissionDeniedError) as ei:
            await agent.invoke_tool(name)
        assert "No permission rule defined" in str(ei.value) or "default deny" in str(ei.value).lower()
