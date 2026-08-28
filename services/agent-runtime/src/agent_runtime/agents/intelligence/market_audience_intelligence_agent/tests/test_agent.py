"""Tests for Market & Audience Intelligence against mock data-ingestion + provider-gateway."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
import uvicorn
from threading import Thread

from agent_contracts.envelope import AgentMessage
from agent_runtime.agents.intelligence.market_audience_intelligence_agent.agent import (
    MarketAudienceIntelligenceAgent,
)
from agent_runtime.agents.intelligence.market_audience_intelligence_agent.config import (
    MarketAudienceConfig,
)
from agent_runtime.agents.intelligence.market_audience_intelligence_agent.data_ingestion_client import (
    MarketDataIngestionClient,
)
from agent_runtime.envelope import AgentMessageEnvelope

REPO_ROOT = Path(__file__).resolve().parents[8]
MOCK_MAIN = REPO_ROOT / "local" / "mock-provider-gateway" / "main.py"
GW_PORT = int(os.environ.get("MAI_TEST_GATEWAY_PORT", "18083"))
INGEST_PORT = int(os.environ.get("MAI_TEST_INGEST_PORT", "18084"))
GW_URL = f"http://127.0.0.1:{GW_PORT}"
INGEST_URL = f"http://127.0.0.1:{INGEST_PORT}"


def _build_ingest_app() -> FastAPI:
    """Minimal mock of data-ingestion-pipeline routes returning job + events."""
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "healthy", "service": "mock-data-ingestion-pipeline"}

    @app.post("/ingest/trends")
    async def ingest_trends(data: dict):
        topic = data.get("topic") or data.get("market_segment") or "general"
        geo = data.get("geo", "US")
        return {
            "job_id": f"trend-{topic}-{geo}",
            "status": "COMPLETED",
            "events_collected": 2,
            "events_normalized": 2,
            "errors": [],
            "events": [
                {
                    "payload": {
                        "topic": topic,
                        "trend_score": 0.91,
                        "volume": 120000,
                        "geo": geo,
                        "confidence": "high",
                    }
                },
                {
                    "payload": {
                        "topic": f"{topic} adjacent",
                        "trend_score": 0.72,
                        "volume": 40000,
                        "geo": geo,
                    }
                },
            ],
        }

    @app.post("/ingest/youtube")
    async def ingest_youtube(data: dict):
        return {
            "job_id": "yt-1",
            "status": "COMPLETED",
            "events_collected": 1,
            "events_normalized": 1,
            "errors": [],
            "events": [{"payload": {"views": 1000, "topic": data.get("topic", "general")}}],
        }

    @app.post("/ingest/competitors")
    async def ingest_competitors(data: dict):
        cid = data.get("competitor_id", "unknown")
        return {
            "job_id": f"comp-{cid}",
            "status": "COMPLETED",
            "events_collected": 1,
            "events_normalized": 1,
            "errors": [],
            "events": [
                {
                    "payload": {
                        "competitor_id": cid,
                        "latest_video_views": 5000,
                        "topic": data.get("topic", "general"),
                    }
                }
            ],
        }

    return app


@pytest.fixture(scope="module")
def mock_services():
    if not MOCK_MAIN.exists():
        pytest.skip(f"mock gateway missing at {MOCK_MAIN}")

    # Start mock data-ingestion
    ingest_app = _build_ingest_app()

    def run_ingest():
        uvicorn.run(ingest_app, host="127.0.0.1", port=INGEST_PORT, log_level="warning")

    t = Thread(target=run_ingest, daemon=True)
    t.start()

    env = {**os.environ, "PORT": str(GW_PORT)}
    proc = subprocess.Popen(
        [sys.executable, str(MOCK_MAIN)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    deadline = time.time() + 20
    gw_ok = ingest_ok = False
    while time.time() < deadline:
        try:
            if not gw_ok and httpx.get(f"{GW_URL}/health", timeout=1.0).status_code == 200:
                gw_ok = True
        except Exception:
            pass
        try:
            if not ingest_ok and httpx.get(f"{INGEST_URL}/health", timeout=1.0).status_code == 200:
                ingest_ok = True
        except Exception:
            pass
        if gw_ok and ingest_ok:
            break
        time.sleep(0.2)
    if not (gw_ok and ingest_ok):
        proc.terminate()
        pytest.fail(f"services not ready gw={gw_ok} ingest={ingest_ok}")

    yield {"gateway": GW_URL, "ingest": INGEST_URL}
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture
def agent(mock_services):
    return MarketAudienceIntelligenceAgent(
        config=MarketAudienceConfig(
            data_ingestion_url=mock_services["ingest"],
            provider_gateway_url=mock_services["gateway"],
            timeout_seconds=30.0,
        )
    )


def _env(payload: dict) -> AgentMessageEnvelope:
    msg = AgentMessage(
        agent_type="market_audience_intelligence_agent",
        task_type="analyze",
        payload={**payload, "task_type": "analyze"},
    )
    return AgentMessageEnvelope(message=msg)


class TestMarketAudienceIntelligenceAgent:
    def test_capabilities(self, agent):
        assert "fetch_trends" in agent.capabilities
        assert "analyze_sentiment" in agent.capabilities
        assert "trend_analysis" in agent.capabilities

    def test_identity(self, agent):
        assert agent.agent_id == "market_audience_intelligence_agent"

    @pytest.mark.asyncio
    async def test_client_calls_ingest_interface(self, mock_services):
        client = MarketDataIngestionClient(base_url=mock_services["ingest"])
        try:
            result = await client.fetch_trends(market_segment="robotics", geo="US")
            assert result["status"] == "COMPLETED"
            assert result["events_normalized"] >= 1
            assert any(
                (e.get("payload") or {}).get("topic") == "robotics" for e in result.get("events", [])
            )
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_execute_uses_ingestion_and_provider(self, agent):
        result = await agent.run(
            _env(
                {
                    "market_segment": "workflow automation",
                    "channels_of_interest": ["ch_demo"],
                    "competitor_channels": ["comp_a"],
                    "time_window_days": 14,
                }
            )
        )
        assert result["raw_provider_text"]
        assert result["ingestion_jobs"]
        assert result["top_trends"]
        # Hardcoded stub phrases must not appear
        blob = str(result)
        assert "Young Professionals" not in blob
        assert "Tool Tuesday" not in blob
        assert "workflow automation tutorial" not in blob or result["raw_provider_text"]

    @pytest.mark.asyncio
    async def test_output_varies_with_segment(self, agent):
        r1 = await agent.run(_env({"market_segment": "marine biology"}))
        r2 = await agent.run(_env({"market_segment": "orbital mechanics"}))
        t1 = [t["topic"] for t in r1["top_trends"]]
        t2 = [t["topic"] for t in r2["top_trends"]]
        assert t1 != t2 or r1["market_summary"] != r2["market_summary"]
        assert any("marine" in t.lower() for t in t1) or "marine" in r1["market_summary"].lower()
        assert any("orbital" in t.lower() for t in t2) or "orbital" in r2["market_summary"].lower()


class TestSchemas:
    def test_request_defaults(self):
        from agent_runtime.agents.intelligence.market_audience_intelligence_agent.schemas import (
            IntelligenceRequest,
        )

        r = IntelligenceRequest()
        assert r.market_segment == "general"
        assert r.time_window_days == 30


class TestPermissionEnforcement:
    @pytest.mark.asyncio
    async def test_revoke_denies_primary_tool(self, mock_services):
        from agent_runtime.tool_permissions import PermissionDeniedError, PermissionMatrix
        matrix = PermissionMatrix()
        for tool in ["fetch_trends","analyze_sentiment"]:
            matrix.revoke("market_audience_intelligence_agent", tool, "execute")
        from agent_runtime.agents.intelligence.market_audience_intelligence_agent.agent import MarketAudienceIntelligenceAgent
        from agent_runtime.agents.intelligence.market_audience_intelligence_agent.config import MarketAudienceConfig
        agent = MarketAudienceIntelligenceAgent(
            config=MarketAudienceConfig(
                provider_gateway_url=mock_services["gateway"],
                data_ingestion_url=mock_services["ingest"],
            ),
            permission_matrix=matrix,
        )
        with pytest.raises(PermissionDeniedError):
            await agent.run(_env({"market_segment": "deny"}))

    @pytest.mark.asyncio
    async def test_never_listed_tool_default_deny(self, agent):
        from agent_runtime.tool_permissions import PermissionDeniedError
        name = "never_listed_tool_zz_mai"
        perm = agent.permissions.matrix.check(agent.agent_id, name, "execute")
        assert perm.decision.value == "deny"
        assert "No permission rule defined" in perm.justification
        async def _dummy() -> str:
            return "nope"
        agent.register_tool(name, _dummy)
        with pytest.raises(PermissionDeniedError) as ei:
            await agent.invoke_tool(name)
        assert "No permission rule defined" in str(ei.value) or "default deny" in str(ei.value).lower()
