"""Fact Verification Agent — verify claims against ResearchBundle / research-service (§4.2)."""
from __future__ import annotations

import logging
from typing import Any

from agent_runtime.agents.base import BaseAgent
from agent_runtime.sandbox.runner import SandboxLimits
from agent_runtime.envelope import AgentMessageEnvelope

from agent_runtime.agents.creative.fact_verification_agent.config import FactVerificationConfig
from agent_runtime.agents.creative.fact_verification_agent.research_service_client import (
    FactCheckServiceClient,
)
from agent_runtime.agents.creative.fact_verification_agent.schemas import (
    FactCheckRequest,
    FactCheckResponse,
    VerificationResult,
)
from agent_runtime.agents.creative.fact_verification_agent.state import FVPhase, FVState
from agent_runtime.agents.creative.fact_verification_agent import tools as fv_tools
from agent_runtime.agents.creative.fact_verification_agent.tools import (
    claims_from_request,
    cross_reference,
    research_context_from_bundle,
    try_parse_json_object,
    verify_claim,
)

logger = logging.getLogger(__name__)

# Map research-service verdicts → agent verdict vocabulary
_VERDICT_MAP = {
    "true": "verified",
    "verified": "verified",
    "false": "false",
    "mostly_false": "false",
    "mixed": "mixed",
    "disputed": "disputed",
    "unverifiable": "unverified",
    "unverified": "unverified",
}


class FactVerificationAgent(BaseAgent[FactCheckResponse]):
    """Cross-references claims against research sources; scores confidence."""

    def __init__(self, config: FactVerificationConfig | None = None, **kwargs: Any) -> None:
        limits = kwargs.pop("sandbox_limits", None) or SandboxLimits(allow_network=True, max_cpu_time_seconds=60.0)
        super().__init__(
            agent_id="fact_verification_agent",
            name="Fact Verification",
            domain="creative",
            version="1.0.0",
            autonomy_level="L2",
            sandbox_limits=limits,
            **kwargs,
        )
        self.config = config or FactVerificationConfig()
        self.register_tool("verify_claim", fv_tools.verify_claim)
        self.register_tool("cross_reference", fv_tools.cross_reference)

    @property
    def capabilities(self) -> list[str]:
        return [
            "claim_verification",
            "source_cross_reference",
            "confidence_scoring",
            "bias_detection",
            "verify_claim",
            "cross_reference",
        ]

    async def execute(self, envelope: AgentMessageEnvelope) -> dict[str, Any]:
        payload = envelope.message.payload or {}
        if "task_type" not in payload and getattr(envelope.message, "task_type", None):
            payload = {**payload, "task_type": envelope.message.task_type}

        request = FactCheckRequest(**payload)
        state = FVState()
        state.advance(FVPhase.VERIFYING)

        claims = claims_from_request(request.claims, request.research_bundle)
        claims = [self.sanitize_input(c, source="claim") for c in claims]
        if not claims:
            return FactCheckResponse(
                verifications=[],
                overall_confidence=0.0,
                unverifiable_count=0,
                contradiction_alerts=["No claims provided"],
                recommendations=["Provide claims or a research_bundle with claims"],
            ).model_dump()

        context = research_context_from_bundle(
            request.research_bundle, request.research_brief
        )
        for seg in request.draft_segments or []:
            context += "\n" + self.sanitize_input(seg, source="draft_segment")

        client = FactCheckServiceClient(
            base_url=self.config.research_service_url,
            token=self.config.research_service_token,
            timeout=self.config.timeout_seconds,
        )
        service_verdicts: list[dict[str, Any]] = []
        try:
            for claim in claims:
                try:
                    result = await self.invoke_tool(
                        "verify_claim",
                        (),
                        {"claim_text": claim, "context": context, "config": self.config, "client": client},
                    )
                except Exception as exc:
                    logger.warning("fact-check failed for claim: %s", exc)
                    result = {
                        "claim_text": claim,
                        "verdict": "unverifiable",
                        "confidence": 0.0,
                        "explanation": f"Service error: {exc}",
                        "sources": [],
                    }
                service_verdicts.append(result)
                state.claim_results.append(result)
        finally:
            await client.close()

        state.advance(FVPhase.CROSS_REF)
        llm = await self.invoke_tool(
            "cross_reference",
            (),
            {"claims": claims, "research_context": context, "service_verdicts": service_verdicts, "config": self.config},
        )
        state.provider_texts.append(llm.content)
        usage = {
            "prompt_tokens": llm.prompt_tokens,
            "completion_tokens": llm.completion_tokens,
            "total_tokens": llm.total_tokens,
            "estimated_cost_usd": llm.cost_usd,
        }
        state.provider_usages.append(usage)

        parsed = try_parse_json_object(llm.content) or {}
        response = self._build_response(
            claims, service_verdicts, parsed, llm.content, usage, request
        )
        state.advance(FVPhase.COMPLETED)
        logger.info(
            "FactVerification claims=%d unverifiable=%d",
            len(claims),
            response.unverifiable_count,
        )
        return response.model_dump()

    def _build_response(
        self,
        claims: list[str],
        service_verdicts: list[dict[str, Any]],
        parsed: dict[str, Any],
        raw_text: str,
        usage: dict[str, Any],
        request: FactCheckRequest,
    ) -> FactCheckResponse:
        threshold = request.min_confidence_threshold or self.config.min_confidence_threshold
        provider_vs = parsed.get("verifications") or parsed.get("results") or []
        verifications: list[VerificationResult] = []

        for i, claim in enumerate(claims):
            svc = service_verdicts[i] if i < len(service_verdicts) else {}
            prov = provider_vs[i] if i < len(provider_vs) and isinstance(provider_vs[i], dict) else {}

            raw_verdict = str(
                prov.get("verdict") or svc.get("verdict") or "unverifiable"
            ).lower()
            verdict = _VERDICT_MAP.get(raw_verdict, raw_verdict)
            raw_conf = prov.get("confidence")
            if raw_conf is None:
                raw_conf = svc.get("confidence")
            confidence = float(raw_conf) if raw_conf is not None else 0.0
            explanation = str(
                prov.get("explanation") or svc.get("explanation") or ""
            )
            sources = svc.get("sources") or []
            supporting = list(prov.get("supporting_sources") or [])
            if not supporting and sources:
                supporting = [
                    str(s.get("title") or s.get("url") or s)
                    if isinstance(s, dict)
                    else str(s)
                    for s in sources[:3]
                ]

            requires_review = (
                confidence < threshold
                or verdict in ("false", "disputed", "unverified", "mixed")
            )
            verifications.append(
                VerificationResult(
                    claim=claim,
                    verdict=verdict,
                    confidence=confidence,
                    supporting_sources=supporting,
                    contradicting_sources=list(prov.get("contradicting_sources") or []),
                    explanation=explanation,
                    requires_human_review=bool(
                        prov.get("requires_human_review", requires_review)
                    ),
                    source_ids=[
                        str(s.get("source_id") or s.get("id") or "")
                        for s in sources
                        if isinstance(s, dict)
                    ],
                )
            )

        confidences = [v.confidence for v in verifications]
        overall = sum(confidences) / len(confidences) if confidences else 0.0
        unverifiable = sum(
            1 for v in verifications if v.verdict in ("unverified", "unverifiable")
        )
        alerts = list(parsed.get("contradiction_alerts") or [])
        for v in verifications:
            if v.verdict in ("false", "disputed", "mixed"):
                alerts.append(f"{v.verdict}: {v.claim[:120]}")

        recommendations = list(parsed.get("recommendations") or [])
        for v in verifications:
            if v.verdict == "false":
                recommendations.append(f"Rewrite or remove false claim: {v.claim[:80]}")
            elif v.requires_human_review:
                recommendations.append(f"Human review needed: {v.claim[:80]}")

        return FactCheckResponse(
            verifications=verifications,
            overall_confidence=overall,
            unverifiable_count=unverifiable,
            contradiction_alerts=alerts,
            recommendations=recommendations,
            raw_provider_text=raw_text,
            provider_usage=usage,
        )
