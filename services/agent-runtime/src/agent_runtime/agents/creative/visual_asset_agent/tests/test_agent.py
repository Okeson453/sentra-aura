from __future__ import annotations
import os, subprocess, sys, time
from pathlib import Path
import httpx, pytest
from agent_contracts.envelope import AgentMessage
from agent_runtime.agents.creative.visual_asset_agent.agent import VisualAssetAgent
from agent_runtime.agents.creative.visual_asset_agent.config import VisualAssetConfig
from agent_runtime.envelope import AgentMessageEnvelope

REPO = Path(__file__).resolve().parents[8]
MOCK = REPO / "local/mock-provider-gateway/main.py"
PORT = int(os.environ.get("VA_TEST_PORT", "18101"))
URL = f"http://127.0.0.1:{PORT}"

@pytest.fixture(scope="module")
def gw():
    proc = subprocess.Popen([sys.executable, str(MOCK)], env={**os.environ, "PORT": str(PORT)}, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for _ in range(100):
        try:
            if httpx.get(f"{URL}/health", timeout=1).status_code == 200:
                break
        except Exception:
            time.sleep(0.2)
    else:
        proc.terminate(); pytest.fail("gw")
    yield URL
    proc.terminate()

@pytest.fixture
def agent(gw):
    return VisualAssetAgent(config=VisualAssetConfig(provider_gateway_url=gw, timeout_seconds=30))

def env(p):
    return AgentMessageEnvelope(message=AgentMessage(agent_type="visual_asset_agent", task_type="generate", payload={**p, "task_type": "generate"}))

@pytest.mark.asyncio
async def test_varies(agent):
    r1 = await agent.run(env({"scene_descriptions": ["deep ocean marine snow"], "asset_budget": 2}))
    r2 = await agent.run(env({"scene_descriptions": ["orbital debris field"], "asset_budget": 2}))
    assert r1["assets"] and r2["assets"]
    assert r1["assets"][0]["image_url"]
    assert "marine" in r1["assets"][0]["prompt"].lower() or "ocean" in r1["assets"][0]["prompt"].lower()
    assert "orbital" in r2["assets"][0]["prompt"].lower() or "debris" in r2["assets"][0]["prompt"].lower()

@pytest.mark.asyncio
async def test_script_handoff(agent):
    r = await agent.run(env({"script": {"hook": "Quantum sensing opens new doors.", "sections": [{"title": "A", "content": "Sensors beat noise.", "b_roll_notes": "lab footage"}]}, "asset_budget": 3}))
    assert len(r["assets"]) >= 1
    assert r["manifest"]["count"] >= 1


class TestPermissionEnforcement:
    @pytest.mark.asyncio
    async def test_revoke_denies(self, gw):
        from agent_runtime.tool_permissions import PermissionDeniedError, PermissionMatrix

        matrix = PermissionMatrix()
        matrix.revoke("visual_asset_agent", "generate_image", "execute")
        matrix.revoke("visual_asset_agent", "edit_image", "execute")
        agent = VisualAssetAgent(
            config=VisualAssetConfig(provider_gateway_url=gw, timeout_seconds=30),
            permission_matrix=matrix,
        )
        with pytest.raises(PermissionDeniedError):
            await agent.run(env({"scene_descriptions": ["x"], "asset_budget": 1}))

    @pytest.mark.asyncio
    async def test_never_listed_default_deny(self, agent):
        from agent_runtime.tool_permissions import PermissionMatrix

        matrix = PermissionMatrix()
        perm = matrix.check("visual_asset_agent", "never_listed_va_tool_zz9", "execute")
        assert perm.decision.value == "deny"
        assert "No permission rule defined" in perm.justification
