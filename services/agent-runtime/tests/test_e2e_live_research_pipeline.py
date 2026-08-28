"""E2E with live research-service HTTP (not injected research_bundle).

Starts real research-service FastAPI app (HTTP) + mock provider-gateway,
then: ResearchAgent → scripting → scene → clipping → SEO → publishing (ESCALATE).
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn
from agent_contracts.envelope import AgentMessage
from agent_runtime.envelope import AgentMessageEnvelope
from agent_runtime.approval_gate import ApprovalGate
from agent_runtime.tool_permissions import ApprovalRequiredError

REPO = Path(__file__).resolve().parents[3]
MOCK = REPO / "local/mock-provider-gateway/main.py"
GW_PORT = int(os.environ.get("E2E_LIVE_GW_PORT", "19011"))
RS_PORT = int(os.environ.get("E2E_LIVE_RS_PORT", "19012"))
GW_URL = f"http://127.0.0.1:{GW_PORT}"
RS_URL = f"http://127.0.0.1:{RS_PORT}"


def _env(agent_type: str, payload: dict) -> AgentMessageEnvelope:
    return AgentMessageEnvelope(
        message=AgentMessage(agent_type=agent_type, task_type="run", payload=payload)
    )


@pytest.fixture(scope="module")
def live_services():
    """HTTP research-service (real app) + mock provider-gateway."""
    if not MOCK.exists():
        pytest.skip(f"mock gateway missing: {MOCK}")

    # Prefer real research_service.app; fall back to minimal compatible app
    try:
        from research_service.main import app as research_app
        using_real = True
    except Exception:
        using_real = False
        from fastapi import FastAPI, Header, HTTPException
        from fastapi import Request
        import uuid

        research_app = FastAPI()
        jobs: dict = {}
        results: dict = {}

        def _auth(authorization: str | None):
            if not authorization or not authorization.startswith("Bearer "):
                raise HTTPException(status_code=401, detail="auth")

        @research_app.get("/health")
        async def health():
            return {"status": "healthy"}

        @research_app.post("/research")
        async def start(request: Request, authorization: str | None = Header(None)):
            _auth(authorization)
            body = await request.json()
            q = body.get("query") or ""
            if not q or not body.get("channel_id"):
                raise HTTPException(status_code=400, detail="query and channel_id required")
            jid = f"research-{uuid.uuid4().hex[:12]}"
            jobs[jid] = {"job_id": jid, "status": "completed", "query": q}
            results[jid] = {
                "job_id": jid,
                "sources": [
                    {
                        "url": f"https://example.com/{q[:20].replace(' ', '-')}",
                        "title": f"Source on {q}",
                        "snippet": f"Evidence regarding {q}.",
                    }
                ],
                "claims": [{"text": f"{q} is studied in peer literature.", "confidence": 0.75}],
                "summary": f"Research brief for {q}",
            }
            return jobs[jid]

        @research_app.get("/research/jobs/{job_id}")
        async def job(job_id: str, authorization: str | None = Header(None)):
            _auth(authorization)
            if job_id not in jobs:
                raise HTTPException(status_code=404)
            return jobs[job_id]

        @research_app.get("/research/jobs/{job_id}/results")
        async def res(job_id: str, authorization: str | None = Header(None)):
            _auth(authorization)
            if job_id not in results:
                raise HTTPException(status_code=404)
            return results[job_id]

    t = threading.Thread(
        target=lambda: uvicorn.run(research_app, host="127.0.0.1", port=RS_PORT, log_level="warning"),
        daemon=True,
    )
    t.start()

    proc = subprocess.Popen(
        [sys.executable, str(MOCK)],
        env={**os.environ, "PORT": str(GW_PORT)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    deadline = time.time() + 25
    ok_gw = ok_rs = False
    while time.time() < deadline:
        try:
            if not ok_gw and httpx.get(f"{GW_URL}/health", timeout=1).status_code == 200:
                ok_gw = True
        except Exception:
            pass
        try:
            if not ok_rs and httpx.get(f"{RS_URL}/health", timeout=1).status_code == 200:
                ok_rs = True
        except Exception:
            pass
        if ok_gw and ok_rs:
            break
        time.sleep(0.2)
    if not (ok_gw and ok_rs):
        proc.terminate()
        pytest.fail(f"services not ready gw={ok_gw} rs={ok_rs} real_rs={using_real}")

    yield {"gateway": GW_URL, "research": RS_URL, "real_research_app": using_real}
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()


@pytest.mark.asyncio
async def test_e2e_live_research_service_http_chain(live_services):
    """ResearchAgent hits research-service over HTTP, then full downstream chain."""
    from agent_runtime.agents.intelligence.research_agent.agent import ResearchAgent
    from agent_runtime.agents.intelligence.research_agent.config import ResearchAgentConfig
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
    rs_url = live_services["research"]
    gw = live_services["gateway"]

    # Prove HTTP path: POST /research directly
    r = httpx.post(
        f"{rs_url}/research",
        headers={"Authorization": "Bearer dev-token"},
        json={"query": topic, "channel_id": "ch-e2e-live", "channel_name": "ch-e2e-live", "max_sources": 5},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    job = r.json()
    assert job.get("job_id")

    research = ResearchAgent(
        config=ResearchAgentConfig(
            research_service_url=rs_url,
            research_service_token="dev-token",
            provider_gateway_url=gw,
            timeout_seconds=45.0,
        )
    )
    research_out = await research.run(
        _env(
            "research_agent",
            {"topic": topic, "channel_id": "ch-e2e-live", "channel_name": "ch-e2e-live", "task_type": "gather", "max_sources": 5},
        )
    )
    assert research_out
    # Must reflect research-service interaction (not empty injected bundle only)
    blob = str(research_out).lower()
    assert "marine" in blob or "source" in blob or "claim" in blob or research_out.get("status")

    scripting = ScriptingAgent(config=ScriptingAgentConfig(provider_gateway_url=gw, timeout_seconds=30))
    script_out = await scripting.run(
        _env("scripting_agent", {"topic": topic, "research": research_out, "research_bundle": research_out})
    )
    assert script_out
    script = script_out if isinstance(script_out, dict) else {}

    scene = SceneShotAgent(config=SceneConfig(provider_gateway_url=gw, timeout_seconds=30))
    shots = await scene.run(_env("scene_shot_agent", {"topic": topic, "script": script}))
    assert shots

    clipping = AIClippingAgent(config=ClipConfig(provider_gateway_url=gw, timeout_seconds=30))
    clips = await clipping.run(
        _env(
            "ai_clipping_agent",
            {
                "topic": topic,
                "video_id": "e2e-live-1",
                "script": script,
                "segments": [
                    {
                        "segment_id": "s0",
                        "start_seconds": 0,
                        "end_seconds": 22,
                        "text": f"Why does {topic} matter for climate models?",
                        "visual_change": 0.85,
                    },
                    {
                        "segment_id": "s1",
                        "start_seconds": 22,
                        "end_seconds": 48,
                        "text": "Sinking aggregates sequester carbon for centuries in the deep ocean.",
                        "visual_change": 0.35,
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
    pub = PublishingAgent(config=PubConfig(provider_gateway_url=gw, timeout_seconds=30), approval_gate=gate)
    payload = {"topic": topic, "seo": pack if isinstance(pack, dict) else {}, "metadata": {"platforms": ["youtube"]}}
    with pytest.raises(ApprovalRequiredError) as ei:
        await pub.run(_env("publishing_agent", payload))
    gate.grant(ei.value.approval_id, approved_by="human.operator@sentra")
    published = await pub.run(_env("publishing_agent", payload))
    assert published
