from __future__ import annotations
import os, subprocess, sys, time
from pathlib import Path
import httpx, pytest
from agent_contracts.envelope import AgentMessage
from agent_runtime.agents.production.scene_shot_agent.agent import SceneShotAgent
from agent_runtime.agents.production.scene_shot_agent.config import AgentConfig
from agent_runtime.envelope import AgentMessageEnvelope
from agent_runtime.tool_permissions import PermissionDeniedError, PermissionMatrix

REPO = Path(__file__).resolve().parents[8]
MOCK = REPO / "local/mock-provider-gateway/main.py"
PORT = int(os.environ.get("SCENE_SHOT_AGENT_PORT", "18110"))
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
    return SceneShotAgent(config=AgentConfig(provider_gateway_url=gw, timeout_seconds=30))

def env(p):
    return AgentMessageEnvelope(message=AgentMessage(agent_type="scene_shot_agent", task_type="plan", payload={**p, "task_type": "plan"}))

@pytest.mark.asyncio
async def test_varies(agent):
    r1 = await agent.run(env({"script": {"hook": "Marine snow descends.", "sections": [{"title": "Deep", "content": "Particles sink."}]}}))
    r2 = await agent.run(env({"script": {"hook": "Debris in orbit.", "sections": [{"title": "Risk", "content": "Collision cascades."}]}}))
    assert r1["shots"] and r2["shots"]
    d1 = r1["shots"][0]["description"].lower()
    d2 = r2["shots"][0]["description"].lower()
    assert d1 != d2 or "marine" in d1 or "debris" in d2 or "orbit" in d2

@pytest.mark.asyncio
async def test_visual_handoff(agent):
    r = await agent.run(env({"script": {"hook": "Lab intro", "sections": [{"title": "A", "content": "Setup"}]}, "visual_assets": [{"asset_id": "va-1"}, {"asset_id": "va-2"}]}))
    assert r["shots"][0].get("visual_asset_id") == "va-1"
    assert r["edl"]

class TestPermissionEnforcement:
    @pytest.mark.asyncio
    async def test_revoke_denies(self, gw):
        matrix = PermissionMatrix()
        matrix.revoke("scene_shot_agent", "plan_shots", "execute")
        agent = SceneShotAgent(config=AgentConfig(provider_gateway_url=gw), permission_matrix=matrix)
        with pytest.raises(PermissionDeniedError):
            await agent.run(env({"script": {"hook": "x"}}))

    @pytest.mark.asyncio
    async def test_never_listed_default_deny(self, agent):
        name = "never_listed_shot_tool_zz"
        perm = agent.permissions.matrix.check(agent.agent_id, name, "execute")
        assert perm.decision.value == "deny"
        assert "No permission rule defined" in perm.justification
        async def _dummy() -> str:
            return "x"
        agent.register_tool(name, _dummy)
        with pytest.raises(PermissionDeniedError) as ei:
            await agent.invoke_tool(name)
        assert "No permission rule defined" in str(ei.value)
