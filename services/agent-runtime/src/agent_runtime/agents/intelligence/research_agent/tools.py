"""Tools for Research Agent.

Permission matrix allows exactly:
  - search_web
  - fetch_source
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from prompt_registry.loader import PromptLoader
from provider_interfaces.llm import LLMConfig, LLMResponse

from agent_runtime.injection_defense.classifier import InjectionClassifier
from agent_runtime.injection_defense.untrusted_boundary import UntrustedBoundary, BoundaryResult
from agent_runtime.agents.intelligence.research_agent.config import ResearchAgentConfig
from agent_runtime.agents.intelligence.research_agent.research_client import ResearchServiceClient
from agent_runtime.agents.intelligence.research_agent.schemas import ResearchRequest, ResearchSource

logger = logging.getLogger(__name__)
_loader = PromptLoader()
_boundary = UntrustedBoundary(classifier=InjectionClassifier())


def render_gather_prompt(context: dict[str, Any], version: str = "v1") -> str:
    return _loader.render(
        agent_id="research_agent",
        prompt_type="gather",
        version=version,
        context=context,
    )


def tag_as_data(text: str, *, source: str, audit: BoundaryResult) -> str:
    """Mark content as DATA (never instruction) after boundary validation.

    Downstream prompts must treat this block as untrusted evidence only.
    """
    return (
        f'<<<UNTRUSTED_DATA role="DATA" source="{source}" '
        f'threat_level="{audit.threat_level}" allowed="{audit.allowed}" '
        f'audit_hash="{audit.audit_hash}">>>\n'
        f"{audit.sanitized_text}\n"
        f"<<<END_UNTRUSTED_DATA>>>"
    )


def apply_untrusted_boundary(
    text: str,
    *,
    source: str = "web",
    agent_id: str = "research_agent",
) -> tuple[str, BoundaryResult]:
    """Run UntrustedBoundary; return (DATA-tagged text, audit)."""
    audit = _boundary.validate(text, source=source, agent_id=agent_id)
    tagged = tag_as_data(text, source=source, audit=audit)
    return tagged, audit


async def search_web(
    request: ResearchRequest,
    *,
    config: ResearchAgentConfig,
    client: ResearchServiceClient | None = None,
) -> dict[str, Any]:
    """Permission tool: search_web — delegates retrieval to research-service."""
    owns = client is None
    client = client or ResearchServiceClient(
        base_url=config.research_service_url,
        token=config.research_service_token,
        timeout=config.timeout_seconds,
        poll_interval=config.poll_interval_seconds,
        poll_max_attempts=config.poll_max_attempts,
    )
    try:
        query = request.initial_query or request.topic
        # REAL_INTEGRATION: research-service
        return await client.search_and_wait(
            query=query,
            depth=request.depth,
            max_sources=request.max_sources,
            topic_domains=request.topic_domains,
            channel_id=(request.channel_name or getattr(request, "channel_id", None) or "default-channel"),
        )
    finally:
        if owns:
            await client.close()


async def fetch_source(
    url: str,
    content: str,
    *,
    source_id: str = "",
    agent_id: str = "research_agent",
) -> tuple[ResearchSource, BoundaryResult]:
    """Permission tool: fetch_source — boundary-validate one retrieved source body."""
    tagged, audit = apply_untrusted_boundary(
        content, source=url or source_id or "fetch_source", agent_id=agent_id
    )
    src = ResearchSource(
        source_id=source_id or audit.audit_hash,
        url=url,
        title="",
        content=tagged if audit.allowed else audit.sanitized_text,
        credibility_score=0.0,
        source_type="web",
        boundary_threat_level=audit.threat_level,
        boundary_allowed=audit.allowed,
    )
    return src, audit


async def synthesize_brief(
    prompt: str,
    *,
    config: ResearchAgentConfig | None = None,
) -> LLMResponse:
    """Provider-gateway synthesis (not a permission-matrix tool name)."""
    cfg = config or ResearchAgentConfig()
    llm_cfg = LLMConfig(
        model=cfg.default_model,
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
        timeout_seconds=cfg.timeout_seconds,
    )
    url = f"{cfg.provider_gateway_url.rstrip('/')}/v1/complete"
    payload = {
        "prompt": prompt,
        "model": llm_cfg.model,
        "temperature": llm_cfg.temperature,
        "max_tokens": llm_cfg.max_tokens,
    }
    logger.info("research synthesize → provider-gateway %s", url)
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


def sources_from_research_results(
    results: dict[str, Any],
    *,
    agent_id: str = "research_agent",
) -> tuple[list[ResearchSource], list[dict[str, Any]]]:
    """Map research-service results → boundary-validated ResearchSource list."""
    raw_sources = (
        results.get("sources")
        or results.get("ranked_sources")
        or (results.get("results") or {}).get("sources")
        or []
    )
    out: list[ResearchSource] = []
    audits: list[dict[str, Any]] = []
    for i, item in enumerate(raw_sources):
        if not isinstance(item, dict):
            continue
        body = str(
            item.get("content")
            or item.get("snippet")
            or item.get("text")
            or item.get("title")
            or ""
        )
        url = str(item.get("url") or "")
        title = str(item.get("title") or f"source_{i}")
        sid = str(item.get("source_id") or item.get("id") or f"src-{i}")
        tagged, audit = apply_untrusted_boundary(
            body, source=url or sid, agent_id=agent_id
        )
        audits.append(
            {
                "source_id": sid,
                "threat_level": audit.threat_level,
                "threat_score": audit.threat_score,
                "allowed": audit.allowed,
                "injection_detected": audit.injection_detected,
                "audit_hash": audit.audit_hash,
            }
        )
        if not audit.allowed:
            # Still record blocked source with redacted body
            content = audit.sanitized_text
        else:
            content = tagged
        out.append(
            ResearchSource(
                source_id=sid,
                url=url,
                title=title,
                content=content,
                credibility_score=float(item.get("credibility_score") or item.get("score") or 0.5),
                source_type=str(item.get("source_type") or "web"),
                boundary_threat_level=audit.threat_level,
                boundary_allowed=audit.allowed,
            )
        )
    return out, audits
