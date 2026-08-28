"""Tools for the Scripting Agent — provider-gateway completion and prompt rendering.

All LLM calls go through the provider-gateway HTTP API (local mock or real).
Prompt templates live in packages/prompt-registry/prompts/scripting_agent/.
Responses are adapted into provider_interfaces.llm.LLMResponse.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from prompt_registry.loader import PromptLoader
from provider_interfaces.llm import LLMConfig, LLMResponse

from agent_runtime.agents.creative.scripting_agent.config import ScriptingAgentConfig

logger = logging.getLogger(__name__)

_loader = PromptLoader()


def render_prompt(
    prompt_type: str,
    context: dict[str, Any],
    version: str = "v1",
) -> str:
    """Render a scripting_agent prompt from the shared prompt-registry."""
    return _loader.render(
        agent_id="scripting_agent",
        prompt_type=prompt_type,
        version=version,
        context=context,
    )


async def call_provider_complete(
    prompt: str,
    *,
    config: ScriptingAgentConfig | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> LLMResponse:
    """Send a completion request to provider-gateway and return an LLMResponse.

    Hits POST {base_url}/v1/complete. No hardcoded fallback text is returned
    when the gateway responds successfully.
    """
    cfg = config or ScriptingAgentConfig()
    llm_cfg = LLMConfig(
        model=model or cfg.default_model,
        temperature=temperature if temperature is not None else cfg.temperature,
        max_tokens=max_tokens if max_tokens is not None else cfg.max_tokens,
        timeout_seconds=cfg.timeout_seconds,
    )
    payload = {
        "prompt": prompt,
        "model": llm_cfg.model,
        "temperature": llm_cfg.temperature,
        "max_tokens": llm_cfg.max_tokens,
    }
    url = f"{cfg.provider_gateway_url.rstrip('/')}/v1/complete"
    logger.info("Calling provider-gateway complete at %s (prompt_len=%d)", url, len(prompt))

    async with httpx.AsyncClient(timeout=httpx.Timeout(llm_cfg.timeout_seconds, connect=10.0)) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

    text = data.get("text") or data.get("content")
    if not text:
        raise RuntimeError(f"provider-gateway response missing text/content: {data!r}")

    usage = data.get("usage") or {}
    result = LLMResponse(
        content=text,
        model=str(data.get("model") or llm_cfg.model),
        prompt_tokens=int(usage.get("prompt_tokens") or 0),
        completion_tokens=int(usage.get("completion_tokens") or 0),
        total_tokens=int(usage.get("total_tokens") or 0),
        latency_ms=float(data.get("latency_ms") or 0.0),
        cost_usd=float(usage.get("estimated_cost_usd") or 0.0),
        provider=str(data.get("provider") or "provider-gateway"),
    )
    logger.info(
        "provider-gateway returned text_len=%d model=%s",
        len(result.content),
        result.model,
    )
    return result


def try_parse_json_object(text: str) -> dict[str, Any] | None:
    """Best-effort extraction of a JSON object from LLM text."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        try:
            return json.loads(fence.group(1))
        except json.JSONDecodeError:
            pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    return None


def script_dict_from_provider_text(
    text: str,
    *,
    video_title: str = "",
    fallback_label: str = "provider",
) -> dict[str, Any]:
    """Build a script structure that always incorporates the provider's real text."""
    parsed = try_parse_json_object(text)
    if parsed and isinstance(parsed.get("script"), dict):
        return parsed["script"]
    if parsed and any(k in parsed for k in ("hook", "intro", "sections", "cta", "outro")):
        return {
            "hook": parsed.get("hook", ""),
            "intro": parsed.get("intro", ""),
            "sections": parsed.get("sections", []),
            "cta": parsed.get("cta", ""),
            "outro": parsed.get("outro", ""),
        }
    if parsed and "rewritten_script" in parsed:
        rs = parsed["rewritten_script"]
        if isinstance(rs, dict):
            return rs

    return {
        "hook": text[:280] if text else f"[{fallback_label}] opening for {video_title}",
        "intro": text[280:560] if len(text) > 280 else text,
        "sections": [
            {
                "title": "Main",
                "content": text,
                "estimated_duration": max(60, len(text.split()) * 2),
                "b_roll_notes": "Derived from provider response",
            }
        ],
        "cta": "Subscribe and comment with your thoughts.",
        "outro": "Thanks for watching.",
    }


def word_count_of_script(script: dict[str, Any]) -> int:
    parts: list[str] = []
    for key in ("hook", "intro", "cta", "outro"):
        val = script.get(key)
        if isinstance(val, str):
            parts.append(val)
    for section in script.get("sections") or []:
        if isinstance(section, dict):
            parts.append(str(section.get("content", "")))
        elif isinstance(section, str):
            parts.append(section)
    return len(" ".join(parts).split())


# --- Permission-matrix tool entrypoints (invoked via BaseAgent.invoke_tool) ---


async def draft_script(
    context: dict[str, Any],
    *,
    config: ScriptingAgentConfig | None = None,
) -> dict[str, Any]:
    """Matrix tool: draft_script — render draft prompt and call provider-gateway."""
    cfg = config or ScriptingAgentConfig()
    prompt = render_prompt("draft", context)
    provider = await call_provider_complete(prompt, config=cfg)
    usage = {
        "prompt_tokens": provider.prompt_tokens,
        "completion_tokens": provider.completion_tokens,
        "total_tokens": provider.total_tokens,
        "estimated_cost_usd": provider.cost_usd,
    }
    script = script_dict_from_provider_text(
        provider.content,
        video_title=str(context.get("video_title") or "Untitled"),
        fallback_label="draft",
    )
    return {"content": provider.content, "usage": usage, "script": script}


async def critique_script(
    context: dict[str, Any],
    *,
    config: ScriptingAgentConfig | None = None,
) -> dict[str, Any]:
    """Matrix tool: critique_script."""
    cfg = config or ScriptingAgentConfig()
    prompt = render_prompt("critique", context)
    provider = await call_provider_complete(prompt, config=cfg)
    usage = {
        "prompt_tokens": provider.prompt_tokens,
        "completion_tokens": provider.completion_tokens,
        "total_tokens": provider.total_tokens,
        "estimated_cost_usd": provider.cost_usd,
    }
    return {"content": provider.content, "usage": usage}


async def rewrite_section(
    context: dict[str, Any],
    *,
    config: ScriptingAgentConfig | None = None,
) -> dict[str, Any]:
    """Matrix tool: rewrite_section."""
    cfg = config or ScriptingAgentConfig()
    prompt = render_prompt("rewrite", context)
    provider = await call_provider_complete(prompt, config=cfg)
    usage = {
        "prompt_tokens": provider.prompt_tokens,
        "completion_tokens": provider.completion_tokens,
        "total_tokens": provider.total_tokens,
        "estimated_cost_usd": provider.cost_usd,
    }
    script = script_dict_from_provider_text(
        provider.content,
        video_title=str(context.get("video_title") or "Untitled"),
        fallback_label="rewrite",
    )
    return {"content": provider.content, "usage": usage, "script": script}
