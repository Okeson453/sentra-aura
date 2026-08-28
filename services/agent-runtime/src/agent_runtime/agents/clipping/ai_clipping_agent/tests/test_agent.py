from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from agent_contracts.envelope import AgentMessage
from agent_runtime.agents.clipping.ai_clipping_agent.agent import AIClippingAgent
from agent_runtime.agents.clipping.ai_clipping_agent.config import AgentConfig
from agent_runtime.envelope import AgentMessageEnvelope
from agent_runtime.tool_permissions import PermissionDeniedError, PermissionMatrix

REPO = Path(__file__).resolve().parents[8]
MOCK = REPO / "local/mock-provider-gateway/main.py"
PORT = int(os.environ.get("AI_CLIPPING__PORT", "18255"))
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
        pytest.fail("gw")
    yield URL
    proc.terminate()



@pytest.fixture(scope="module")
def clipping_engine():
    """Real clipping-engine FastAPI app on a local port (Architecture §6 scoring owner)."""
    import socket
    import threading
    from uvicorn import Config, Server
    try:
        from clipping_engine.main import app as ce_app
    except Exception as exc:
        pytest.skip(f"clipping-engine not importable: {exc}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    url = f"http://127.0.0.1:{port}"

    config = Config(ce_app, host="127.0.0.1", port=port, log_level="warning")
    server = Server(config)

    def _run():
        import asyncio
        asyncio.run(server.serve())

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    for _ in range(100):
        try:
            if httpx.get(f"{url}/health", timeout=1).status_code == 200:
                break
        except Exception:
            time.sleep(0.2)
    else:
        server.should_exit = True
        pytest.fail("clipping-engine not ready")
    yield url
    server.should_exit = True



@pytest.fixture
def agent(gw, clipping_engine):
    return AIClippingAgent(
        config=AgentConfig(
            provider_gateway_url=gw,
            clipping_engine_url=clipping_engine,
            timeout_seconds=30,
        )
    )


def env(p):
    return AgentMessageEnvelope(
        message=AgentMessage(agent_type="ai_clipping_agent", task_type="select_clips", payload={**p, "task_type": "select_clips"})
    )


def _marine_segments():
    return [
        {
            "segment_id": "s0",
            "start_seconds": 0,
            "end_seconds": 18,
            "text": "Why does marine snow never truly settle? The answer reshapes ocean carbon models.",
            "visual_change": 0.9,
        },
        {
            "segment_id": "s1",
            "start_seconds": 18,
            "end_seconds": 40,
            "text": "Marine snow forms when plankton die and aggregate into sinking particles.",
            "visual_change": 0.3,
        },
        {
            "segment_id": "s2",
            "start_seconds": 40,
            "end_seconds": 58,
            "text": "They carry carbon into the abyss after that event.",  # context-dependent
            "visual_change": 0.2,
        },
        {
            "segment_id": "s3",
            "start_seconds": 58,
            "end_seconds": 85,
            "text": "Satellite data shows export flux varies with seasonal blooms and storms.",
            "visual_change": 0.5,
        },
    ]


def _orbit_segments():
    return [
        {
            "segment_id": "o0",
            "start_seconds": 0,
            "end_seconds": 20,
            "text": "What if a single collision triggers an orbital debris cascade?",
            "visual_change": 0.85,
        },
        {
            "segment_id": "o1",
            "start_seconds": 20,
            "end_seconds": 45,
            "text": "Kessler syndrome predicts runaway collisions in low earth orbit within decades.",
            "visual_change": 0.4,
        },
        {
            "segment_id": "o2",
            "start_seconds": 45,
            "end_seconds": 70,
            "text": "Active debris removal concepts include nets, harpoons, and laser nudging.",
            "visual_change": 0.35,
        },
    ]


@pytest.mark.asyncio
async def test_output_varies_with_domain_content(agent):
    r1 = await agent.run(env({"video_id": "v-marine", "segments": _marine_segments(), "topic": "marine snow"}))
    r2 = await agent.run(env({"video_id": "v-orbit", "segments": _orbit_segments(), "topic": "orbital debris"}))
    assert r1["status"] == "ok" and r2["status"] == "ok"
    assert r1["candidates"] and r2["candidates"]
    t1 = " ".join(c["text"] for c in r1["candidates"]).lower()
    t2 = " ".join(c["text"] for c in r2["candidates"]).lower()
    assert "marine" in t1 or "plankton" in t1
    assert "debris" in t2 or "orbital" in t2 or "kessler" in t2
    assert t1 != t2


@pytest.mark.asyncio
async def test_composite_scores_present_and_ordered(agent):
    r = await agent.run(env({"video_id": "v1", "segments": _marine_segments(), "max_clips": 3}))
    assert r["candidates"]
    scores = [c["scores"]["composite"] for c in r["candidates"]]
    assert scores == sorted(scores, reverse=True)
    for c in r["candidates"]:
        s = c["scores"]
        for key in ("hook", "emotion", "density", "narrative", "novelty", "composite"):
            assert key in s
            assert 0.0 <= float(s[key]) <= 1.0


@pytest.mark.asyncio
async def test_context_dependency_flagged_by_engine(agent):
    """Engine scores context_dependency; agent surfaces context_complete."""
    r = await agent.run(
        env({
            "video_id": "v-ctx",
            "segments": _marine_segments(),
            "max_clips": 5,
            "score_threshold": 0.1,
        })
    )
    all_c = list(r.get("candidates") or []) + list(r.get("rejected") or [])
    assert all_c
    # Pronoun-heavy segment should exist among scored results
    dependent = [c for c in all_c if "they carry carbon" in (c.get("text") or "").lower()
                 or "abyss" in (c.get("text") or "").lower()]
    assert dependent, "expected pronoun-heavy segment to appear"
    # Engine feature scores must be present
    assert "scores" in dependent[0]
    assert "context_dependency" in dependent[0]["scores"]


@pytest.mark.asyncio
async def test_dedup_rejects_near_duplicate_segments(agent):
    segs = [
        {"segment_id": "a", "start_seconds": 0, "end_seconds": 20,
         "text": "Why orbital debris cascades threaten every satellite in LEO today?", "visual_change": 0.9},
        {"segment_id": "b", "start_seconds": 20, "end_seconds": 40,
         "text": "Why orbital debris cascades threaten every satellite in LEO today?", "visual_change": 0.9},
        {"segment_id": "c", "start_seconds": 40, "end_seconds": 65,
         "text": "Laser nudging offers a non-contact method for raising debris perigee.", "visual_change": 0.4},
    ]
    r = await agent.run(env({"video_id": "v-dup", "segments": segs, "max_clips": 3, "score_threshold": 0.2}))
    selected_texts = [c["text"] for c in r["candidates"]]
    # Should not select both identical hooks
    assert selected_texts.count(segs[0]["text"]) <= 1
    assert any(rsn.get("rejected_reason") == "duplicate_of_selected" for rsn in r["rejected"]) or len(r["candidates"]) <= 2


@pytest.mark.asyncio
async def test_script_fallback_still_produces_candidates(agent):
    r = await agent.run(
        env({
            "video_id": "v-script",
            "topic": "marine snow ecology",
            "script": {
                "hook": "Why is the deep ocean snowing carbon?",
                "sections": [
                    {"title": "Formation", "content": "Plankton blooms collapse and particles aggregate into marine snow."},
                    {"title": "Export", "content": "The flux exports carbon that can sequester for centuries."},
                ],
            },
        })
    )
    assert r["segment_count"] >= 1
    assert r["candidates"] or r["rejected"]


class TestPermissionEnforcement:
    @pytest.mark.asyncio
    async def test_revoke_denies(self, gw):
        matrix = PermissionMatrix()
        matrix.revoke("ai_clipping_agent", "select_clips", "execute")
        agent = AIClippingAgent(config=AgentConfig(provider_gateway_url=gw), permission_matrix=matrix)
        with pytest.raises(PermissionDeniedError):
            await agent.run(env({"topic": "deny-probe", "segments": _marine_segments()}))

    @pytest.mark.asyncio
    async def test_never_listed_default_deny(self, agent):
        name = "never_listed_clip_zz"
        perm = agent.permissions.matrix.check(agent.agent_id, name, "execute")
        assert perm.decision.value == "deny"
        assert "No permission rule defined" in perm.justification

        async def _dummy() -> str:
            return "x"

        agent.register_tool(name, _dummy)
        with pytest.raises(PermissionDeniedError) as ei:
            await agent.invoke_tool(name)
        assert "No permission rule defined" in str(ei.value)
