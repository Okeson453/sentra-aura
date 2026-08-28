"""Tests for Fact Verification Agent."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from threading import Thread

import httpx
import pytest
from fastapi import FastAPI, Header, HTTPException
import uvicorn

from agent_contracts.envelope import AgentMessage
from agent_runtime.agents.creative.fact_verification_agent.agent import FactVerificationAgent
from agent_runtime.agents.creative.fact_verification_agent.config import FactVerificationConfig
from agent_runtime.envelope import AgentMessageEnvelope

# Prefer real research_agent schema for integration test
try:
    from agent_runtime.agents.intelligence.research_agent.schemas import (
        ResearchClaim,
        ResearchResponse,
        ResearchSource,
    )
    HAS_RESEARCH_SCHEMA = True
except ImportError:
    HAS_RESEARCH_SCHEMA = False

REPO_ROOT = Path(__file__).resolve().parents[8]
MOCK_MAIN = REPO_ROOT / "local" / "mock-provider-gateway" / "main.py"
GW_PORT = int(os.environ.get("FACT_TEST_GATEWAY_PORT", "18094"))
RS_PORT = int(os.environ.get("FACT_TEST_RS_PORT", "18095"))
GW_URL = f"http://127.0.0.1:{GW_PORT}"
RS_URL = f"http://127.0.0.1:{RS_PORT}"


def _build_research_app() -> FastAPI:
    app = FastAPI()

    def _auth(authorization: str | None = Header(None)) -> None:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="unauthorized")

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    @app.post("/fact-check")
    async def fact_check(body: dict, authorization: str | None = Header(None)):
        _auth(authorization)
        claim = (body.get("claim_text") or "").lower()
        # Deterministic fixtures for true / false / unverifiable
        if "moon is made of cheese" in claim or "pigs can fly" in claim:
            return {
                "claim_text": body.get("claim_text"),
                "verdict": "false",
                "confidence": 0.92,
                "explanation": "Contradicted by established scientific consensus.",
                "sources": [{"title": "Astronomy FAQ", "url": "https://example.com/astro", "credibility_score": 0.95}],
            }
        if "earth orbits the sun" in claim or "water boils at 100" in claim:
            return {
                "claim_text": body.get("claim_text"),
                "verdict": "true",
                "confidence": 0.95,
                "explanation": "Supported by high-credibility sources.",
                "sources": [{"title": "Physics textbook", "url": "https://example.com/phys", "credibility_score": 0.98}],
            }
        if "always" in claim or "never" in claim:
            return {
                "claim_text": body.get("claim_text"),
                "verdict": "mixed",
                "confidence": 0.4,
                "explanation": "Absolute language; evidence is mixed.",
                "sources": [],
            }
        return {
            "claim_text": body.get("claim_text"),
            "verdict": "unverifiable",
            "confidence": 0.2,
            "explanation": "Insufficient evidence.",
            "sources": [],
        }

    return app


@pytest.fixture(scope="module")
def mock_services():
    if not MOCK_MAIN.exists():
        pytest.skip(f"mock gateway missing: {MOCK_MAIN}")
    app = _build_research_app()
    Thread(
        target=lambda: uvicorn.run(app, host="127.0.0.1", port=RS_PORT, log_level="warning"),
        daemon=True,
    ).start()
    proc = subprocess.Popen(
        [sys.executable, str(MOCK_MAIN)],
        env={**os.environ, "PORT": str(GW_PORT)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    deadline = time.time() + 20
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
        pytest.fail(f"services not ready gw={ok_gw} rs={ok_rs}")
    yield {"gateway": GW_URL, "research": RS_URL}
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture
def agent(mock_services):
    return FactVerificationAgent(
        config=FactVerificationConfig(
            research_service_url=mock_services["research"],
            research_service_token="dev-token",
            provider_gateway_url=mock_services["gateway"],
            timeout_seconds=30.0,
            min_confidence_threshold=0.6,
        )
    )


def _env(payload: dict) -> AgentMessageEnvelope:
    return AgentMessageEnvelope(
        message=AgentMessage(
            agent_type="fact_verification_agent",
            task_type="verify",
            payload={**payload, "task_type": "verify"},
        )
    )


class TestFactVerificationAgent:
    def test_capabilities(self, agent):
        assert "verify_claim" in agent.capabilities
        assert "cross_reference" in agent.capabilities

    def test_identity(self, agent):
        assert agent.agent_id == "fact_verification_agent"

    @pytest.mark.asyncio
    async def test_false_claim_flagged(self, agent):
        result = await agent.run(
            _env({"claims": ["The Moon is made of cheese"]})
        )
        assert result["verifications"]
        v = result["verifications"][0]
        assert v["verdict"] == "false"
        assert v["confidence"] >= 0.6
        assert v["requires_human_review"] is True
        assert any("false" in a.lower() for a in result.get("contradiction_alerts") or [])

    @pytest.mark.asyncio
    async def test_true_claim_verified(self, agent):
        result = await agent.run(
            _env({"claims": ["The Earth orbits the Sun"]})
        )
        v = result["verifications"][0]
        assert v["verdict"] == "verified"
        assert v["confidence"] >= 0.8

    @pytest.mark.asyncio
    async def test_mixed_results_vary(self, agent):
        result = await agent.run(
            _env(
                {
                    "claims": [
                        "The Earth orbits the Sun",
                        "Pigs can fly unaided at sea level",
                    ]
                }
            )
        )
        verdicts = {v["claim"]: v["verdict"] for v in result["verifications"]}
        assert verdicts["The Earth orbits the Sun"] == "verified"
        assert verdicts["Pigs can fly unaided at sea level"] == "false"
        assert result["raw_provider_text"]

    @pytest.mark.asyncio
    async def test_consumes_research_bundle_schema(self, agent):
        """Handoff: research_agent ResearchResponse → fact_verification research_bundle."""
        if not HAS_RESEARCH_SCHEMA:
            pytest.skip("research_agent schemas not importable")
        bundle = ResearchResponse(
            executive_summary="Brief on orbital mechanics.",
            key_findings=[{"finding": "Earth orbits the Sun", "confidence": "high"}],
            sources=[
                ResearchSource(
                    source_id="s1",
                    url="https://example.com/orbit",
                    title="Orbital mechanics",
                    content="Earth orbits the Sun in an elliptical path.",
                    credibility_score=0.9,
                )
            ],
            claims=[
                ResearchClaim(
                    claim_text="The Earth orbits the Sun",
                    confidence=0.8,
                    source_ids=["s1"],
                ),
                ResearchClaim(
                    claim_text="The Moon is made of cheese",
                    confidence=0.1,
                    source_ids=[],
                ),
            ],
            confidence_score=0.7,
        )
        # Use model_dump — exact research_agent output shape
        result = await agent.run(
            _env({"research_bundle": bundle.model_dump(), "claims": []})
        )
        assert len(result["verifications"]) >= 2
        by_claim = {v["claim"]: v["verdict"] for v in result["verifications"]}
        assert by_claim.get("The Earth orbits the Sun") == "verified"
        assert by_claim.get("The Moon is made of cheese") == "false"


class TestSchemas:
    def test_request_accepts_bundle(self):
        from agent_runtime.agents.creative.fact_verification_agent.schemas import FactCheckRequest

        r = FactCheckRequest(research_bundle={"claims": [{"claim_text": "x"}]})
        assert r.research_bundle is not None


class TestPermissionEnforcement:
    @pytest.mark.asyncio
    async def test_revoke_denies_primary_tool(self, mock_services):
        from agent_runtime.tool_permissions import PermissionDeniedError, PermissionMatrix
        matrix = PermissionMatrix()
        for tool in ["verify_claim","cross_reference"]:
            matrix.revoke("fact_verification_agent", tool, "execute")
        from agent_runtime.agents.creative.fact_verification_agent.agent import FactVerificationAgent
        from agent_runtime.agents.creative.fact_verification_agent.config import FactVerificationConfig
        agent = FactVerificationAgent(
            config=FactVerificationConfig(
                provider_gateway_url=mock_services["gateway"],
                research_service_url=mock_services["research"],
                research_service_token="dev-token",
            ),
            permission_matrix=matrix,
        )
        with pytest.raises(PermissionDeniedError):
            await agent.run(_env({"claims": ["deny probe claim"]}))

    @pytest.mark.asyncio
    async def test_never_listed_tool_default_deny(self, agent):
        from agent_runtime.tool_permissions import PermissionDeniedError
        name = "never_listed_tool_zz_fv"
        perm = agent.permissions.matrix.check(agent.agent_id, name, "execute")
        assert perm.decision.value == "deny"
        assert "No permission rule defined" in perm.justification
        async def _dummy() -> str:
            return "nope"
        agent.register_tool(name, _dummy)
        with pytest.raises(PermissionDeniedError) as ei:
            await agent.invoke_tool(name)
        assert "No permission rule defined" in str(ei.value) or "default deny" in str(ei.value).lower()
