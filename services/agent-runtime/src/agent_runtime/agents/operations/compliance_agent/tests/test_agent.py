from __future__ import annotations
import os, subprocess, sys, time
from pathlib import Path
import httpx, pytest
from agent_contracts.envelope import AgentMessage
from agent_runtime.agents.operations.compliance_agent.agent import ComplianceAgent
from agent_runtime.agents.operations.compliance_agent.config import AgentConfig
from agent_runtime.envelope import AgentMessageEnvelope
from agent_runtime.tool_permissions import PermissionDeniedError, PermissionMatrix

REPO = Path(__file__).resolve().parents[8]
MOCK = REPO / "local/mock-provider-gateway/main.py"
PORT = int(os.environ.get("COMPLIANCE_A_PORT", "18369"))
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
    return ComplianceAgent(config=AgentConfig(provider_gateway_url=gw, timeout_seconds=30))

def env(p):
    return AgentMessageEnvelope(message=AgentMessage(agent_type="compliance_agent", task_type="run", payload={**p, "task_type": "run"}))

@pytest.mark.asyncio
async def test_output_varies(agent):
    r1 = await agent.run(env({"topic": "marine snow ecology", "content": {"text": "ocean"}, "script": {"hook": "Marine snow"}}))
    r2 = await agent.run(env({"topic": "orbital debris mitigation", "content": {"text": "space"}, "script": {"hook": "Debris"}}))
    assert r1["status"] and r2["status"]
    b1 = (r1.get("raw_provider_text") or "") + str(r1.get("result"))
    b2 = (r2.get("raw_provider_text") or "") + str(r2.get("result"))
    assert b1 != b2 or "marine" in b1.lower() or "orbital" in b2.lower()


class TestPermissionEnforcement:
    @pytest.mark.asyncio
    async def test_revoke_denies(self, gw):
        matrix = PermissionMatrix()
        for tool in ['check_compliance']:
            matrix.revoke("compliance_agent", tool, "execute")
        agent = ComplianceAgent(config=AgentConfig(provider_gateway_url=gw), permission_matrix=matrix)
        with pytest.raises(PermissionDeniedError):
            await agent.run(env({"topic": "deny-probe"}))

    @pytest.mark.asyncio
    async def test_never_listed_default_deny(self, agent):
        name = "never_listed_compliance_zz"
        perm = agent.permissions.matrix.check(agent.agent_id, name, "execute")
        assert perm.decision.value == "deny"
        assert "No permission rule defined" in perm.justification
        async def _dummy() -> str:
            return "x"
        agent.register_tool(name, _dummy)
        with pytest.raises(PermissionDeniedError) as ei:
            await agent.invoke_tool(name)
        assert "No permission rule defined" in str(ei.value)
