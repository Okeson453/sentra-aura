"""Tools for Fact Verification Agent.

Permission matrix allows exactly:
  - verify_claim
  - cross_reference
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from prompt_registry.loader import PromptLoader
from provider_interfaces.llm import LLMConfig, LLMResponse

from agent_runtime.agents.creative.fact_verification_agent.config import FactVerificationConfig
from agent_runtime.agents.creative.fact_verification_agent.research_service_client import (
    FactCheckServiceClient,
)

logger = logging.getLogger(__name__)
_loader = PromptLoader()


def render_verify_prompt(context: dict[str, Any], version: str = "v1") -> str:
    return _loader.render(
        agent_id="fact_verification_agent",
        prompt_type="verify",
        version=version,
        context=context,
    )


async def verify_claim(
    claim_text: str,
    *,
    context: str = "",
    config: FactVerificationConfig,
    client: FactCheckServiceClient | None = None,
) -> dict[str, Any]:
    """Permission tool: verify_claim — research-service /fact-check."""
    owns = client is None
    client = client or FactCheckServiceClient(
        base_url=config.research_service_url,
        token=config.research_service_token,
        timeout=config.timeout_seconds,
    )
    try:
        # REAL_INTEGRATION: research-service
        return await client.fact_check(claim_text=claim_text, context=context)
    finally:
        if owns:
            await client.close()


async def cross_reference(
    claims: list[str],
    research_context: str,
    service_verdicts: list[dict[str, Any]],
    *,
    config: FactVerificationConfig,
) -> LLMResponse:
    """Permission tool: cross_reference — provider-gateway synthesis of verdicts."""
    context = {
        "claims": claims,
        "research_brief": research_context[:4000],
        "min_confidence_threshold": config.min_confidence_threshold,
        "service_verdicts": json.dumps(service_verdicts)[:4000],
    }
    prompt = render_verify_prompt(context)
    prompt += (
        "\n\n## Service-level fact-check results (DATA)\n"
        f"{json.dumps(service_verdicts)[:4000]}\n"
    )
    llm_cfg = LLMConfig(
        model=config.default_model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        timeout_seconds=config.timeout_seconds,
    )
    url = f"{config.provider_gateway_url.rstrip('/')}/v1/complete"
    payload = {
        "prompt": prompt,
        "model": llm_cfg.model,
        "temperature": llm_cfg.temperature,
        "max_tokens": llm_cfg.max_tokens,
    }
    logger.info("cross_reference → provider-gateway %s", url)
    async with httpx.AsyncClient(timeout=httpx.Timeout(llm_cfg.timeout_seconds, connect=10.0)) as http:
        response = await http.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
    text = data.get("text") or data.get("content")
    if not text:
        raise RuntimeError(f"provider-gateway missing text: {data!r}")
    usage = data.get("usage") or {}
    return LLMResponse(
        content=text,
        model=str(data.get("model") or llm_cfg.model),
        prompt_tokens=int(usage.get("prompt_tokens") or 0),
        completion_tokens=int(usage.get("completion_tokens") or 0),
        total_tokens=int(usage.get("total_tokens") or 0),
        latency_ms=float(data.get("latency_ms") or 0.0),
        cost_usd=float(usage.get("estimated_cost_usd") or 0.0),
        provider=str(data.get("provider") or "provider-gateway"),
    )


def try_parse_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        try:
            return json.loads(fence.group(1))
        except json.JSONDecodeError:
            pass
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    return None


def claims_from_request(request_claims: list[str], research_bundle: dict[str, Any] | None) -> list[str]:
    """Extract claim texts from explicit list and/or ResearchBundle.claims."""
    out: list[str] = []
    for c in request_claims or []:
        if c and str(c).strip():
            out.append(str(c).strip())
    if research_bundle:
        for c in research_bundle.get("claims") or []:
            if isinstance(c, dict):
                t = c.get("claim_text") or c.get("text")
                if t:
                    out.append(str(t).strip())
            elif isinstance(c, str) and c.strip():
                out.append(c.strip())
        # key_findings may also carry claim-like statements
        for f in research_bundle.get("key_findings") or []:
            if isinstance(f, dict):
                t = f.get("finding") or f.get("text")
                if t and str(t) not in out:
                    out.append(str(t).strip())
    # de-dupe preserve order
    seen: set[str] = set()
    unique: list[str] = []
    for c in out:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


def research_context_from_bundle(bundle: dict[str, Any] | None, brief: str = "") -> str:
    if brief:
        return brief
    if not bundle:
        return ""
    parts: list[str] = []
    if bundle.get("executive_summary"):
        parts.append(str(bundle["executive_summary"]))
    for s in bundle.get("sources") or []:
        if isinstance(s, dict):
            parts.append(
                f"{s.get('title', '')}: {str(s.get('content', ''))[:400]}"
            )
    return "\n".join(parts)
