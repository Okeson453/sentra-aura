"""Tests for Voice Agent."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from agent_contracts.envelope import AgentMessage
from agent_runtime.agents.creative.voice_agent.agent import VoiceAgent
from agent_runtime.agents.creative.voice_agent.config import VoiceAgentConfig
from agent_runtime.envelope import AgentMessageEnvelope

try:
    from agent_runtime.agents.creative.scripting_agent.schemas import ScriptResponse

    HAS_SCRIPTING = True
except ImportError:
    HAS_SCRIPTING = False

REPO_ROOT = Path(__file__).resolve().parents[8]
MOCK_MAIN = REPO_ROOT / "local" / "mock-provider-gateway" / "main.py"
GW_PORT = int(os.environ.get("VOICE_TEST_GATEWAY_PORT", "18097"))
GW_URL = f"http://127.0.0.1:{GW_PORT}"


@pytest.fixture(scope="module")
def mock_gateway():
    if not MOCK_MAIN.exists():
        pytest.skip(f"missing {MOCK_MAIN}")
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
    return VoiceAgent(
        config=VoiceAgentConfig(provider_gateway_url=mock_gateway, timeout_seconds=30.0)
    )


def _env(payload: dict) -> AgentMessageEnvelope:
    return AgentMessageEnvelope(
        message=AgentMessage(
            agent_type="voice_agent",
            task_type="synthesize",
            payload={**payload, "task_type": "synthesize"},
        )
    )


class TestVoiceAgent:
    def test_capabilities(self, agent):
        assert "synthesize_speech" in agent.capabilities

    def test_identity(self, agent):
        assert agent.agent_id == "voice_agent"

    @pytest.mark.asyncio
    async def test_tts_called_and_varies(self, agent):
        r1 = await agent.run(
            _env(
                {
                    "script": {
                        "hook": "Marine snow falls through the deep ocean.",
                        "sections": [
                            {"title": "Body", "content": "Particles aggregate and sink."}
                        ],
                    },
                    "voice_profile": "documentary",
                }
            )
        )
        r2 = await agent.run(
            _env(
                {
                    "script": {
                        "hook": "Orbital debris threatens active satellites.",
                        "sections": [
                            {"title": "Body", "content": "Mitigation needs active removal."}
                        ],
                    },
                    "voice_profile": "documentary",
                }
            )
        )
        assert r1["segments"]
        assert r2["segments"]
        assert r1["segments"][0]["audio_url"]
        assert r1["segments"][0]["word_timings"]
        assert r1["segments"][0]["text"] != r2["segments"][0]["text"]
        assert r1["total_duration_seconds"] > 0
        # No old stub default
        assert "Default voiceover text" not in r1["segments"][0]["text"]

    @pytest.mark.asyncio
    async def test_scripting_agent_handoff(self, agent):
        if not HAS_SCRIPTING:
            pytest.skip("scripting schemas unavailable")
        # Real ScriptResponse shape
        sr = ScriptResponse(
            script={
                "hook": "Pattern interrupt about quantum sensing.",
                "intro": "Here is why it matters.",
                "sections": [
                    {
                        "title": "Point One",
                        "content": "Quantum sensors beat classical limits.",
                        "estimated_duration": 60,
                    }
                ],
                "cta": "Subscribe for more physics.",
                "outro": "Thanks for watching.",
            },
            word_count=40,
            estimated_duration=120,
        )
        result = await agent.run(
            _env({"script_response": sr.model_dump(), "script": {}})
        )
        texts = " ".join(s["text"] for s in result["segments"]).lower()
        assert "quantum" in texts
        assert len(result["segments"]) >= 3


class TestPermissionEnforcement:
    @pytest.mark.asyncio
    async def test_revoke_denies_primary_tool(self, mock_gateway):
        from agent_runtime.tool_permissions import PermissionDeniedError, PermissionMatrix
        matrix = PermissionMatrix()
        for tool in ["synthesize_speech","plan_delivery"]:
            matrix.revoke("voice_agent", tool, "execute")
        from agent_runtime.agents.creative.voice_agent.agent import VoiceAgent
        from agent_runtime.agents.creative.voice_agent.config import VoiceAgentConfig
        agent = VoiceAgent(
            config=VoiceAgentConfig(provider_gateway_url=mock_gateway),
            permission_matrix=matrix,
        )
        with pytest.raises(PermissionDeniedError):
            await agent.run(_env({"script": {"hook": "deny"}, "task_type": "synthesize"}))

    @pytest.mark.asyncio
    async def test_never_listed_tool_default_deny(self, agent):
        from agent_runtime.tool_permissions import PermissionDeniedError
        name = "never_listed_tool_zz_voice"
        perm = agent.permissions.matrix.check(agent.agent_id, name, "execute")
        assert perm.decision.value == "deny"
        assert "No permission rule defined" in perm.justification
        async def _dummy() -> str:
            return "nope"
        agent.register_tool(name, _dummy)
        with pytest.raises(PermissionDeniedError) as ei:
            await agent.invoke_tool(name)
        assert "No permission rule defined" in str(ei.value) or "default deny" in str(ei.value).lower()
