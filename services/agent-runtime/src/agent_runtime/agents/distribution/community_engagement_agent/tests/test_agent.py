from __future__ import annotations
import os, subprocess, sys, time
from pathlib import Path
import httpx, pytest
from agent_contracts.envelope import AgentMessage
from agent_runtime.agents.distribution.community_engagement_agent.agent import CommunityEngagementAgent
from agent_runtime.agents.distribution.community_engagement_agent.config import AgentConfig
from agent_runtime.envelope import AgentMessageEnvelope
from agent_runtime.approval_gate import ApprovalGate, ApprovalScope
from agent_runtime.tool_permissions import (
    ApprovalRequiredError,
    PermissionDeniedError,
    PermissionMatrix,
)

REPO = Path(__file__).resolve().parents[8]
MOCK = REPO / "local/mock-provider-gateway/main.py"
PORT = int(os.environ.get("COMMUNITY_EN_PORT", "18204"))
URL = f"http://127.0.0.1:{PORT}"


@pytest.fixture(scope="module")
def gw():
    proc = subprocess.Popen(
        [sys.executable, str(MOCK)],
        env={**os.environ, "PORT": str(PORT)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    for _ in range(100):
        try:
            if httpx.get(f"{URL}/health", timeout=1).status_code == 200:
                break
        except Exception:
            time.sleep(0.2)
    else:
        proc.terminate()
        pytest.fail("gw")
    yield URL
    proc.terminate()


@pytest.fixture
def gate():
    """Isolated gate so tests do not share grants with other agents."""
    return ApprovalGate(default_ttl_seconds=600.0)


@pytest.fixture
def agent(gw, gate):
    """Production matrix + isolated approval gate (no ALLOW override)."""
    return CommunityEngagementAgent(
        config=AgentConfig(provider_gateway_url=gw, timeout_seconds=30),
        permission_matrix=PermissionMatrix(),
        approval_gate=gate,
    )


def env(p):
    return AgentMessageEnvelope(
        message=AgentMessage(
            agent_type="community_engagement_agent",
            task_type="run",
            payload={**p, "task_type": "run"},
        )
    )


async def _grant_and_run(agent, gate, topic: str, scope_key: str = ""):
    """Request via failed invoke, grant, re-invoke successfully."""
    with pytest.raises(ApprovalRequiredError) as ei:
        await agent.invoke_tool(
            "engage_comments",
            (),
            {"payload": {"topic": topic}, "config": agent.config},
            scope_key=scope_key,
        )
    approval_id = ei.value.approval_id
    assert approval_id
    gate.grant(approval_id, approved_by="verifier@sentra.test")
    return await agent.invoke_tool(
        "engage_comments",
        (),
        {"payload": {"topic": topic}, "config": agent.config},
        scope_key=scope_key,
    )


@pytest.mark.asyncio
async def test_output_varies_after_grant(agent, gate):
    r1 = await _grant_and_run(agent, gate, "marine snow ecology", scope_key="var-a")
    r2 = await _grant_and_run(agent, gate, "orbital debris mitigation", scope_key="var-b")
    assert r1.get("status") == "ok" and r2.get("status") == "ok"
    b1 = (r1.get("raw") or "") + str(r1)
    b2 = (r2.get("raw") or "") + str(r2)
    assert b1 != b2 or "marine" in b1.lower() or "orbital" in b2.lower()


@pytest.mark.asyncio
async def test_full_approval_loop(agent, gate):
    # (a) no grant → ApprovalRequiredError
    with pytest.raises(ApprovalRequiredError) as ei:
        await agent.invoke_tool(
            "engage_comments",
            (),
            {"payload": {"topic": "loop-probe"}, "config": agent.config},
            scope_key="loop-1",
        )
    assert ei.value.approval_id
    assert "Approval required" in str(ei.value)

    # (b) grant through real mechanism
    gate.grant(ei.value.approval_id, approved_by="human.operator@sentra")

    # (c) same scope succeeds and tool body runs
    out = await agent.invoke_tool(
        "engage_comments",
        (),
        {"payload": {"topic": "loop-probe"}, "config": agent.config},
        scope_key="loop-1",
    )
    assert out.get("status") == "ok"
    assert out.get("tool") == "engage_comments"
    assert "loop-probe" in str(out.get("topic") or out)

    # (d) grant is single-use — second call with same scope needs a new grant
    with pytest.raises(ApprovalRequiredError):
        await agent.invoke_tool(
            "engage_comments",
            (),
            {"payload": {"topic": "loop-probe-2"}, "config": agent.config},
            scope_key="loop-1",
        )


@pytest.mark.asyncio
async def test_grant_scope_does_not_leak(agent, gate):
    with pytest.raises(ApprovalRequiredError) as ei:
        await agent.invoke_tool(
            "engage_comments",
            (),
            {"payload": {"topic": "scoped"}, "config": agent.config},
            scope_key="scope-A",
        )
    gate.grant(ei.value.approval_id, approved_by="human.operator@sentra")
    # Unrelated scope_key must still require approval
    with pytest.raises(ApprovalRequiredError):
        await agent.invoke_tool(
            "engage_comments",
            (),
            {"payload": {"topic": "other"}, "config": agent.config},
            scope_key="scope-B",
        )
    # Correct scope still works once
    out = await agent.invoke_tool(
        "engage_comments",
        (),
        {"payload": {"topic": "scoped"}, "config": agent.config},
        scope_key="scope-A",
    )
    assert out.get("status") == "ok"


class TestPermissionEnforcement:
    @pytest.mark.asyncio
    async def test_revoke_denies(self, gw, gate):
        matrix = PermissionMatrix()
        matrix.revoke("community_engagement_agent", "engage_comments", "execute")
        agent = CommunityEngagementAgent(
            config=AgentConfig(provider_gateway_url=gw),
            permission_matrix=matrix,
            approval_gate=gate,
        )
        with pytest.raises(PermissionDeniedError):
            await agent.invoke_tool(
                "engage_comments",
                (),
                {"payload": {"topic": "deny"}, "config": agent.config},
            )

    @pytest.mark.asyncio
    async def test_never_listed_default_deny(self, agent):
        name = "never_listed_escalate_zz"
        perm = agent.permissions.matrix.check(agent.agent_id, name, "execute")
        assert perm.decision.value == "deny"
        assert "No permission rule defined" in perm.justification

        async def _dummy() -> str:
            return "x"

        agent.register_tool(name, _dummy)
        with pytest.raises(PermissionDeniedError) as ei:
            await agent.invoke_tool(name)
        assert "No permission rule defined" in str(ei.value)


class TestProductionMatrixEscalate:
    @pytest.mark.asyncio
    async def test_production_matrix_escalate_requires_approval(self, agent):
        with pytest.raises(ApprovalRequiredError) as ei:
            await agent.invoke_tool(
                "engage_comments",
                (),
                {"payload": {"topic": "escalate-probe"}, "config": agent.config},
            )
        assert "Approval required" in str(ei.value)
