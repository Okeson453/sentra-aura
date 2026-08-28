"""Tools for Market & Audience Intelligence Agent.

Permission matrix (tool_permissions.py) allows exactly:
  - fetch_trends
  - analyze_sentiment
Names must match those strings literally.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from prompt_registry.loader import PromptLoader
from provider_interfaces.llm import LLMConfig, LLMResponse

from agent_runtime.agents.intelligence.market_audience_intelligence_agent.config import (
    MarketAudienceConfig,
)
from agent_runtime.agents.intelligence.market_audience_intelligence_agent.data_ingestion_client import (
    MarketDataIngestionClient,
)
from agent_runtime.agents.intelligence.market_audience_intelligence_agent.schemas import (
    IntelligenceRequest,
    TrendSignal,
)

logger = logging.getLogger(__name__)
_loader = PromptLoader()


def render_analyze_prompt(context: dict[str, Any], version: str = "v1") -> str:
    return _loader.render(
        agent_id="market_audience_intelligence_agent",
        prompt_type="analyze",
        version=version,
        context=context,
    )


async def fetch_trends(
    request: IntelligenceRequest,
    *,
    config: MarketAudienceConfig,
    client: MarketDataIngestionClient | None = None,
) -> dict[str, Any]:
    """Permission tool name: fetch_trends — sole consumer of data-ingestion-pipeline trends."""
    owns = client is None
    client = client or MarketDataIngestionClient(
        base_url=config.data_ingestion_url, timeout=config.timeout_seconds
    )
    try:
        # REAL_INTEGRATION: data-ingestion-pipeline
        trends_job = await client.fetch_trends(
            market_segment=request.market_segment,
            geo=request.geo,
            time_window_days=request.time_window_days,
            channels_of_interest=request.channels_of_interest,
        )
        yt_job: dict[str, Any] | None = None
        if request.channels_of_interest:
            # REAL_INTEGRATION: data-ingestion-pipeline
            yt_job = await client.fetch_youtube_signals(
                channel_id=request.channels_of_interest[0],
                market_segment=request.market_segment,
            )
        competitor_jobs: list[dict[str, Any]] = []
        if request.competitor_channels:
            # REAL_INTEGRATION: data-ingestion-pipeline
            competitor_jobs = await client.fetch_competitors(
                competitor_channels=request.competitor_channels,
                market_segment=request.market_segment,
            )
        return {
            "trends_job": trends_job,
            "youtube_job": yt_job,
            "competitor_jobs": competitor_jobs,
        }
    finally:
        if owns:
            await client.close()


async def analyze_sentiment(
    prompt: str,
    *,
    config: MarketAudienceConfig | None = None,
) -> LLMResponse:
    """Permission tool name: analyze_sentiment — synthesis via provider-gateway."""
    cfg = config or MarketAudienceConfig()
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
    logger.info("analyze_sentiment → provider-gateway %s", url)
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


def signals_from_ingestion(jobs: dict[str, Any], market_segment: str) -> list[TrendSignal]:
    """Extract TrendSignal list from ingestion responses (events or job metadata)."""
    signals: list[TrendSignal] = []
    trends_job = jobs.get("trends_job") or {}
    events = trends_job.get("events") or trends_job.get("signals") or []
    for ev in events:
        payload = ev.get("payload") if isinstance(ev, dict) else {}
        if not isinstance(payload, dict):
            payload = ev if isinstance(ev, dict) else {}
        topic = str(payload.get("topic") or market_segment)
        score = float(payload.get("trend_score") or payload.get("opportunity_score") or 0.5)
        signals.append(
            TrendSignal(
                topic=topic,
                velocity=min(1.0, score),
                saturation=float(payload.get("saturation") or max(0.0, 1.0 - score)),
                opportunity_score=round(score * 100 if score <= 1.0 else score, 2),
                confidence=str(payload.get("confidence") or "medium"),
                volume=int(payload.get("volume") or 0),
                source=str(payload.get("source") or "data_ingestion_pipeline"),
            )
        )
    if not signals:
        # Job ran but events were published to the bus only — still record segment focus
        status = trends_job.get("status") or "UNKNOWN"
        signals.append(
            TrendSignal(
                topic=market_segment,
                velocity=0.5,
                saturation=0.5,
                opportunity_score=50.0,
                confidence="low" if status != "COMPLETED" else "medium",
                volume=int(trends_job.get("events_normalized") or 0),
                source="data_ingestion_pipeline",
            )
        )
    return signals
