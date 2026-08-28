"""Tests for Scripting Agent against local mock-provider-gateway."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from agent_runtime.agents.creative.scripting_agent.agent import ScriptingAgent
from agent_runtime.agents.creative.scripting_agent.config import ScriptingAgentConfig
from agent_contracts.envelope import AgentMessage
from agent_runtime.envelope import AgentMessageEnvelope

REPO_ROOT = Path(__file__).resolve().parents[8]
MOCK_MAIN = REPO_ROOT / "local" / "mock-provider-gateway" / "main.py"
MOCK_PORT = int(os.environ.get("SCRIPTING_TEST_GATEWAY_PORT", "18081"))
MOCK_URL = f"http://127.0.0.1:{MOCK_PORT}"


@pytest.fixture(scope="module")
def mock_gateway():
    """Start local/mock-provider-gateway for this test module."""
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
            r = httpx.get(f"{MOCK_URL}/health", timeout=1.0)
            if r.status_code == 200:
                ready = True
                break
        except Exception:
            time.sleep(0.2)
    if not ready:
        proc.terminate()
        out, err = proc.communicate(timeout=5)
        pytest.fail(f"mock gateway failed to start: {err.decode() or out.decode()}")

    yield MOCK_URL
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture
def agent(mock_gateway):
    cfg = ScriptingAgentConfig(
        provider_gateway_url=mock_gateway,
        max_reflection_rounds=1,
        timeout_seconds=30.0,
    )
    return ScriptingAgent(config=cfg)


def _envelope(task_type: str, payload: dict) -> AgentMessageEnvelope:
    msg = AgentMessage(
        agent_type="scripting_agent",
        task_type=task_type,
        payload={**payload, "task_type": task_type},
    )
    return AgentMessageEnvelope(message=msg)


class TestScriptingAgent:
    def test_capabilities(self, agent):
        assert "script_draft" in agent.capabilities
        assert "script_critique" in agent.capabilities
        assert "script_rewrite" in agent.capabilities
        assert "reflection_loop" in agent.capabilities
        assert "sponsorship_injection" in agent.capabilities

    def test_agent_identity(self, agent):
        assert agent.agent_id == "scripting_agent"

    @pytest.mark.asyncio
    async def test_draft_uses_provider_response(self, agent, mock_gateway):
        env = _envelope(
            "draft",
            {
                "video_title": "How to Build a SaaS",
                "channel_name": "Startup Guide",
                "target_length": "15 minutes",
                "tone": "professional",
                "target_keywords": ["SaaS", "startup", "MVP"],
                "max_reflection_rounds": 1,
            },
        )
        result = await agent.run(env)

        assert "script" in result
        assert result["word_count"] > 0
        assert result["raw_provider_text"], "must retain real provider text"
        script_blob = str(result["script"])
        assert "You won't believe what we discovered" not in script_blob
        assert "Here is where the deep dive happens" not in script_blob
        # Structured mock returns DRAFT marker or rewrite path after loop
        assert "[DRAFT-" in script_blob or "[REWRITE-" in script_blob or result["raw_provider_text"]

    @pytest.mark.asyncio
    async def test_full_loop_rewrite_differs_from_draft(self, agent, mock_gateway):
        """Critique step must change the script — rewrite ≠ original draft."""
        env = _envelope(
            "full_loop",
            {
                "video_title": "Retention Mechanics 101",
                "channel_name": "Creator Lab",
                "max_reflection_rounds": 1,
            },
        )
        result = await agent.run(env)
        assert result["reflection_rounds"] >= 1
        assert result["raw_provider_text"]
        assert result.get("critique") is not None
        script_blob = str(result["script"])
        # Mock rewrite returns REWRITE- marker; draft alone would be DRAFT-
        assert "[REWRITE-" in script_blob, "expected rewrite output after critique"
        assert "[DRAFT-" not in result["script"].get("hook", "")

    @pytest.mark.asyncio
    async def test_sponsorship_injection_when_present(self, agent, mock_gateway):
        env = _envelope(
            "draft",
            {
                "video_title": "Best Tools for Devs",
                "channel_name": "Dev Daily",
                "max_reflection_rounds": 1,
                "sponsorship": {
                    "sponsor_name": "CloudHost",
                    "product_name": "CloudHost Pro",
                    "talking_points": ["Deploy in 60 seconds", "Free tier available"],
                    "placement": "mid-roll",
                    "disclosure_required": True,
                },
            },
        )
        result = await agent.run(env)
        assert result["sponsorship_applied"] is True
        blob = str(result["script"])
        assert "CloudHost" in blob
        assert "sponsored" in blob.lower() or "Sponsor" in blob

    @pytest.mark.asyncio
    async def test_sponsorship_skipped_when_absent(self, agent, mock_gateway):
        env = _envelope(
            "draft",
            {
                "video_title": "No Sponsor Video",
                "channel_name": "Solo Channel",
                "max_reflection_rounds": 1,
            },
        )
        result = await agent.run(env)
        assert result["sponsorship_applied"] is False
        blob = str(result["script"]).lower()
        assert "sponsored by" not in blob

    @pytest.mark.asyncio
    async def test_critique_mode(self, agent, mock_gateway):
        existing = {
            "hook": "Old hook",
            "intro": "Old intro",
            "sections": [{"title": "A", "content": "Body", "estimated_duration": 60, "b_roll_notes": ""}],
            "cta": "Subscribe",
            "outro": "Bye",
        }
        env = _envelope(
            "critique",
            {
                "video_title": "Test Video",
                "existing_script": existing,
            },
        )
        result = await agent.run(env)
        assert result["critique"] is not None
        assert result["raw_provider_text"]


class TestPermissionEnforcement:
    """Proof that invoke_tool + matrix are real, not decorative."""

    @pytest.mark.asyncio
    async def test_draft_script_denied_without_matrix_rule(self, mock_gateway):
        from agent_runtime.tool_permissions import (
            PermissionDecision,
            PermissionMatrix,
            ToolPermission,
            PermissionDeniedError,
        )

        # Matrix with scripting tools intentionally omitted → default deny
        empty = PermissionMatrix(custom_permissions=[
            ToolPermission(
                "unrelated_agent", "noop", "execute", PermissionDecision.ALLOW, "x"
            )
        ])
        # Rebuild without DEFAULT_PERMISSIONS: PermissionMatrix always loads defaults.
        # Strip scripting rules by revoking them.
        matrix = PermissionMatrix()
        matrix.revoke("scripting_agent", "draft_script", "execute")
        matrix.revoke("scripting_agent", "critique_script", "execute")
        matrix.revoke("scripting_agent", "rewrite_section", "execute")

        cfg = ScriptingAgentConfig(
            provider_gateway_url=mock_gateway,
            max_reflection_rounds=1,
            timeout_seconds=30.0,
        )
        agent = ScriptingAgent(config=cfg, permission_matrix=matrix)

        with pytest.raises(PermissionDeniedError):
            await agent.run(
                _envelope(
                    "draft",
                    {
                        "video_title": "Permission deny probe",
                        "channel_name": "Test",
                        "task_type": "draft",
                    },
                )
            )

    @pytest.mark.asyncio
    async def test_invoke_tool_records_tool_call(self, agent, mock_gateway):
        result = await agent.run(
            _envelope(
                "draft",
                {
                    "video_title": "Tool call audit probe",
                    "channel_name": "Test",
                    "task_type": "draft",
                    "max_reflection_rounds": 1,
                },
            )
        )
        assert result.get("script")
        # BaseAgent.state.tool_calls populated by invoke_tool
        names = [c.get("tool") for c in agent.state.tool_calls]
        assert "draft_script" in names
        assert any(c.get("success") for c in agent.state.tool_calls)


    @pytest.mark.asyncio
    async def test_never_listed_tool_default_deny(self, agent):
        """Tool name with no matrix row at all must default-deny (not revoke path)."""
        from agent_runtime.tool_permissions import PermissionDeniedError

        never_listed = "totally_unlisted_tool_xyz_9f3a"

        # Confirm matrix has no rule for this name
        perm = agent.permissions.matrix.check(agent.agent_id, never_listed, "execute")
        assert perm.decision.value == "deny"
        assert "No permission rule defined" in perm.justification

        async def _dummy_tool() -> str:
            return "should-not-run"

        agent.register_tool(never_listed, _dummy_tool)

        with pytest.raises(PermissionDeniedError) as excinfo:
            await agent.invoke_tool(never_listed)

        err = str(excinfo.value)
        assert "Permission denied" in err
        assert never_listed in err
        assert "No permission rule defined" in err or "default deny" in err.lower()


class TestSandboxNetworkFlag:
    """allow_network is enforced in sandbox (see agent_runtime.tests.sandbox)."""

    @pytest.mark.asyncio
    async def test_allow_network_false_blocks_httpx(self, mock_gateway):
        from agent_runtime.agents.base import BaseAgent
        from agent_runtime.sandbox.runner import SandboxLimits
        from agent_runtime.tool_permissions import (
            PermissionDecision,
            PermissionMatrix,
            ToolPermission,
        )
        import httpx

        matrix = PermissionMatrix(
            custom_permissions=[
                ToolPermission(
                    "net_probe_agent",
                    "http_get",
                    "execute",
                    PermissionDecision.ALLOW,
                    "test probe",
                )
            ]
        )

        class NetProbeAgent(BaseAgent[dict]):
            def __init__(self) -> None:
                super().__init__(
                    agent_id="net_probe_agent",
                    name="NetProbe",
                    domain="test",
                    permission_matrix=matrix,
                    sandbox_limits=SandboxLimits(allow_network=False, max_cpu_time_seconds=15.0),
                )
                self.register_tool("http_get", self._http_get)

            @property
            def capabilities(self) -> list[str]:
                return ["http_get"]

            async def execute(self, envelope):  # pragma: no cover
                return {}

            async def _http_get(self, url: str) -> dict:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    r = await client.get(url)
                    return {"status_code": r.status_code}

        probe = NetProbeAgent()
        with pytest.raises(RuntimeError) as ei:
            await probe.invoke_tool("http_get", args=(mock_gateway + "/health",))
        assert "Network egress denied" in str(ei.value)
