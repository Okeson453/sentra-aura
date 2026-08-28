"""Tools for Portfolio Strategy Agent.

Permission matrix allows exactly: analyze_portfolio
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from prompt_registry.loader import PromptLoader
from provider_interfaces.llm import LLMConfig, LLMResponse

from agent_runtime.agents.intelligence.portfolio_strategy_agent.config import (
    PortfolioStrategyConfig,
)

logger = logging.getLogger(__name__)
_loader = PromptLoader()


def render_plan_prompt(context: dict[str, Any], version: str = "v1") -> str:
    return _loader.render(
        agent_id="portfolio_strategy_agent",
        prompt_type="plan",
        version=version,
        context=context,
    )


async def analyze_portfolio(
    prompt: str,
    *,
    config: PortfolioStrategyConfig | None = None,
) -> LLMResponse:
    """Permission tool name: analyze_portfolio — provider-gateway synthesis."""
    cfg = config or PortfolioStrategyConfig()
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
    logger.info("analyze_portfolio → provider-gateway %s (prompt_len=%d)", url, len(prompt))
    async with httpx.AsyncClient(timeout=httpx.Timeout(llm_cfg.timeout_seconds, connect=10.0)) as client:
        response = await client.post(url, json=payload)
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
