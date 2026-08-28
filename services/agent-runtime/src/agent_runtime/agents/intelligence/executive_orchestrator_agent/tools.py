"""Tools for Executive Orchestrator — provider-gateway + prompt-registry."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from prompt_registry.loader import PromptLoader
from provider_interfaces.llm import LLMConfig, LLMResponse

from agent_runtime.agents.intelligence.executive_orchestrator_agent.config import (
    ExecutiveOrchestratorConfig,
)

logger = logging.getLogger(__name__)
_loader = PromptLoader()


def render_strategy_prompt(context: dict[str, Any], version: str = "v1") -> str:
    return _loader.render(
        agent_id="executive_orchestrator_agent",
        prompt_type="strategy",
        version=version,
        context=context,
    )


async def call_provider_complete(
    prompt: str,
    *,
    config: ExecutiveOrchestratorConfig | None = None,
) -> LLMResponse:
    """POST /v1/complete on provider-gateway; return real LLMResponse."""
    cfg = config or ExecutiveOrchestratorConfig()
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
    logger.info("ExecutiveOrchestrator → provider-gateway %s (prompt_len=%d)", url, len(prompt))

    async with httpx.AsyncClient(timeout=httpx.Timeout(llm_cfg.timeout_seconds, connect=10.0)) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

    text = data.get("text") or data.get("content")
    if not text:
        raise RuntimeError(f"provider-gateway response missing text/content: {data!r}")

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


async def plan_workflow(
    context: dict[str, Any],
    *,
    config: ExecutiveOrchestratorConfig | None = None,
) -> dict[str, Any]:
    """Matrix tool: plan_workflow — strategy LLM via provider-gateway."""
    cfg = config or ExecutiveOrchestratorConfig()
    prompt = render_strategy_prompt(context)
    llm = await call_provider_complete(prompt, config=cfg)
    return {
        "content": llm.content,
        "usage": {
            "prompt_tokens": llm.prompt_tokens,
            "completion_tokens": llm.completion_tokens,
            "total_tokens": llm.total_tokens,
            "estimated_cost_usd": llm.cost_usd,
        },
    }


async def dispatch_task(
    request_payload: dict[str, Any],
    strategy: dict[str, Any],
) -> dict[str, Any]:
    """Matrix tool: dispatch_task — build assignments + workflow DAG."""
    from agent_runtime.agents.intelligence.executive_orchestrator_agent.coordination import (
        build_agent_assignments,
        build_workflow_dag,
        coordination_notes,
    )
    from agent_runtime.agents.intelligence.executive_orchestrator_agent.schemas import StrategyRequest

    request = StrategyRequest(**request_payload)
    assignments = build_agent_assignments(request, strategy)
    dag = build_workflow_dag(assignments)
    notes = coordination_notes(request, strategy)
    return {
        "agent_assignments": assignments,
        "workflow_dag": dag,
        "coordination_notes": notes,
    }
