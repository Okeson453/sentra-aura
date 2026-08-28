"""End-to-end pipeline: research bundle -> scripting -> production -> clipping -> packaging -> publishing.

Uses real agent classes with mock-provider-gateway. Publishing requires documented ESCALATE approval.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from agent_contracts.envelope import AgentMessage
from agent_runtime.envelope import AgentMessageEnvelope
from agent_runtime.approval_gate import ApprovalGate
from agent_runtime.tool_permissions import ApprovalRequiredError

REPO = Path(__file__).resolve().parents[3]
MOCK = REPO / "local/mock-provider-gateway/main.py"
PORT = int(os.environ.get("E2E_PIPELINE_PORT", "18999"))
URL = f"http://127.0.0.1:{PORT}"


@pytest.fixture(scope="module")
def gw():
    if not MOCK.exists():
        pytest.skip(f"mock gateway missing at {MOCK}")
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
        pytest.fail("gateway did not start")
    yield URL
    proc.terminate()


def _env(agent_type: str, payload: dict):
    return AgentMessageEnvelope(
        message=AgentMessage(agent_type=agent_type, task_type="run", payload=payload)
    )


@pytest.mark.asyncio
async def test_e2e_pipeline_topic_to_publish_packages(gw):
    from agent_runtime.agents.creative.scripting_agent.agent import ScriptingAgent
    from agent_runtime.agents.creative.scripting_agent.config import ScriptingAgentConfig
    from agent_runtime.agents.production.scene_shot_agent.agent import SceneShotAgent
    from agent_runtime.agents.production.scene_shot_agent.config import AgentConfig as SceneConfig
    from agent_runtime.agents.clipping.ai_clipping_agent.agent import AIClippingAgent
    from agent_runtime.agents.clipping.ai_clipping_agent.config import AgentConfig as ClipConfig
    from agent_runtime.agents.distribution.seo_packaging_agent.agent import SEOPackagingAgent
    from agent_runtime.agents.distribution.seo_packaging_agent.config import AgentConfig as SEOConfig
    from agent_runtime.agents.distribution.publishing_agent.agent import PublishingAgent
    from agent_runtime.agents.distribution.publishing_agent.config import AgentConfig as PubConfig

    topic = "marine snow carbon export"
    # Research-service is an external dependency; use a real-shaped research bundle handoff.
    research_bundle = {
        "topic": topic,
        "sources": [
            {"url": "https://example.com/marine-snow", "title": "Marine snow review", "snippet": "Aggregates export carbon."}
        ],
        "claims": [{"text": "Marine snow exports carbon to the deep ocean.", "confidence": 0.8}],
    }

    scripting = ScriptingAgent(config=ScriptingAgentConfig(provider_gateway_url=gw, timeout_seconds=30))
    s = await scripting.run(
        _env("scripting_agent", {"topic": topic, "research": research_bundle, "research_bundle": research_bundle})
    )
    assert s
    script = s if isinstance(s, dict) else {}

    scene = SceneShotAgent(config=SceneConfig(provider_gateway_url=gw, timeout_seconds=30))
    shots = await scene.run(_env("scene_shot_agent", {"topic": topic, "script": script}))
    assert shots

    clipping = AIClippingAgent(config=ClipConfig(provider_gateway_url=gw, timeout_seconds=30))
    clips = await clipping.run(
        _env(
            "ai_clipping_agent",
            {
                "topic": topic,
                "video_id": "e2e-vid-1",
                "script": script,
                "segments": [
                    {
                        "segment_id": "s0",
                        "start_seconds": 0,
                        "end_seconds": 25,
                        "text": f"Why does {topic} reshape ocean models?",
                        "visual_change": 0.9,
                    },
                    {
                        "segment_id": "s1",
                        "start_seconds": 25,
                        "end_seconds": 50,
                        "text": "Particles aggregate and sink, exporting carbon for centuries.",
                        "visual_change": 0.4,
                    },
                ],
            },
        )
    )
    assert clips.get("candidates") is not None

    seo = SEOPackagingAgent(config=SEOConfig(provider_gateway_url=gw, timeout_seconds=30))
    pack = await seo.run(_env("seo_packaging_agent", {"topic": topic, "script": script}))
    assert pack

    gate = ApprovalGate()
    pub = PublishingAgent(
        config=PubConfig(provider_gateway_url=gw, timeout_seconds=30),
        approval_gate=gate,
    )
    payload = {
        "topic": topic,
        "seo": pack if isinstance(pack, dict) else {},
        "metadata": {"platforms": ["youtube"]},
    }
    with pytest.raises(ApprovalRequiredError) as ei:
        await pub.run(_env("publishing_agent", payload))
    assert ei.value.approval_id
    gate.grant(ei.value.approval_id, approved_by="human.operator@sentra")
    published = await pub.run(_env("publishing_agent", payload))
    assert published
    # Documented human-approval gate is the only intervening control for publish.
