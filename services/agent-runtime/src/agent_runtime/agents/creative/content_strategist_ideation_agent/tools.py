"""Tools for Content Strategist & Ideation Agent.

Permission matrix allows exactly:
  - generate_concepts
  - score_ideas
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from prompt_registry.loader import PromptLoader
from provider_interfaces.llm import LLMConfig, LLMResponse

from agent_runtime.agents.creative.content_strategist_ideation_agent.config import (
    ContentStrategistConfig,
)
from agent_runtime.agents.creative.content_strategist_ideation_agent.schemas import (
    IdeationRequest,
    VideoConcept,
)

logger = logging.getLogger(__name__)
_loader = PromptLoader()


def render_ideate_prompt(context: dict[str, Any], version: str = "v1") -> str:
    return _loader.render(
        agent_id="content_strategist_ideation_agent",
        prompt_type="ideate",
        version=version,
        context=context,
    )


def build_context(request: IdeationRequest) -> dict[str, Any]:
    research = request.research_brief
    if isinstance(research, dict):
        research_text = research.get("executive_summary") or json.dumps(research)[:2000]
    else:
        research_text = str(research or "")

    market = request.market_intelligence or {}
    market_text = ""
    if market:
        market_text = str(market.get("market_summary") or "")
        trends = market.get("top_trends") or []
        if trends:
            market_text += "\nTrends: " + json.dumps(trends[:5])

    return {
        "topic": request.topic,
        "channel_name": request.channel_name,
        "target_audience": request.target_audience,
        "content_pillars": request.content_pillars,
        "num_concepts": request.num_concepts,
        "research_brief": research_text,
        "market_intelligence": market_text,
        "market_summary": market.get("market_summary", ""),
        "top_trends": market.get("top_trends") or [],
    }


async def _complete(prompt: str, *, config: ContentStrategistConfig) -> LLMResponse:
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
    logger.info("content_strategist → provider-gateway %s", url)
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


async def generate_concepts(
    request: IdeationRequest,
    *,
    config: ContentStrategistConfig,
) -> LLMResponse:
    """Permission tool: generate_concepts — provider-gateway ideation."""
    context = build_context(request)
    prompt = render_ideate_prompt(context)
    prompt += (
        f"\n\n## Request specifics\n"
        f"Topic: {request.topic}\n"
        f"Channel: {request.channel_name}\n"
        f"Audience: {request.target_audience}\n"
        f"Num concepts: {request.num_concepts}\n"
        f"Pillars: {', '.join(request.content_pillars)}\n"
    )
    if context.get("market_intelligence"):
        prompt += f"\n## Market intelligence\n{context['market_intelligence']}\n"
    if context.get("research_brief"):
        prompt += f"\n## Research brief\n{context['research_brief']}\n"
    return await _complete(prompt, config=config)


async def score_ideas(
    concepts: list[VideoConcept],
    *,
    topic: str,
    config: ContentStrategistConfig,
) -> list[VideoConcept]:
    """Permission tool: score_ideas — rank concepts (provider-assisted)."""
    if not concepts:
        return concepts
    # Local deterministic scoring from existing fields + light provider optional
    scored: list[VideoConcept] = []
    for c in concepts:
        trend_w = {"very high": 1.0, "high": 0.85, "medium": 0.6, "low": 0.3}.get(
            (c.trend_alignment or "medium").lower(), 0.5
        )
        uniq = float(c.uniqueness_score or 0.5)
        # Prefer titles that mention the topic
        topic_hit = 0.15 if topic and topic.lower() in (c.title or "").lower() else 0.0
        score = min(1.0, 0.45 * uniq + 0.4 * trend_w + topic_hit)
        data = c.model_dump()
        data["score"] = round(score, 3)
        scored.append(VideoConcept(**data))
    scored.sort(key=lambda x: x.score, reverse=True)
    return scored


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


def concepts_from_parsed(parsed: dict[str, Any], topic: str) -> list[VideoConcept]:
    raw = parsed.get("concepts") or parsed.get("ideas") or []
    out: list[VideoConcept] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        out.append(
            VideoConcept(
                title=str(item.get("title") or f"{topic} concept"),
                hook=str(item.get("hook") or ""),
                angle=str(item.get("angle") or item.get("format_angle") or ""),
                format=str(item.get("format") or "long-form"),
                thumbnail_concept=str(item.get("thumbnail_concept") or item.get("thumbnail") or ""),
                target_keywords=list(item.get("target_keywords") or item.get("keywords") or []),
                estimated_ctr=str(item.get("estimated_ctr") or ""),
                production_complexity=str(item.get("production_complexity") or "medium"),
                uniqueness_score=float(item.get("uniqueness_score") or 0.5),
                trend_alignment=str(item.get("trend_alignment") or "medium"),
                score=float(item.get("score") or 0.0),
            )
        )
    return out
