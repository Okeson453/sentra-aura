"""Tools for Voice Agent.

Permission matrix:
  - synthesize_speech (ALLOW)
  - clone_voice (ESCALATE — not auto-executed)
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from prompt_registry.loader import PromptLoader
from provider_interfaces.llm import LLMConfig, LLMResponse

from agent_runtime.agents.creative.voice_agent.config import VoiceAgentConfig

logger = logging.getLogger(__name__)
_loader = PromptLoader()


def render_synthesize_prompt(context: dict[str, Any], version: str = "v1") -> str:
    return _loader.render(
        agent_id="voice_agent",
        prompt_type="synthesize",
        version=version,
        context=context,
    )


def extract_script_texts(script: dict[str, Any]) -> list[tuple[str, str]]:
    """Pull ordered (section_id, text) from scripting_agent script body."""
    parts: list[tuple[str, str]] = []
    if not script:
        return parts
    # Flat string body
    if isinstance(script.get("text"), str) and script["text"].strip():
        parts.append(("main", script["text"].strip()))
        return parts
    for key in ("hook", "intro", "cta", "outro"):
        val = script.get(key)
        if isinstance(val, str) and val.strip():
            parts.append((key, val.strip()))
    for i, sec in enumerate(script.get("sections") or []):
        if isinstance(sec, dict):
            content = str(sec.get("content") or sec.get("text") or "").strip()
            title = str(sec.get("title") or f"section_{i}")
            if content:
                parts.append((title, content))
        elif isinstance(sec, str) and sec.strip():
            parts.append((f"section_{i}", sec.strip()))
    return parts


async def synthesize_speech(
    text: str,
    *,
    voice: str,
    config: VoiceAgentConfig,
    speed: float = 1.0,
) -> dict[str, Any]:
    """Permission tool: synthesize_speech — provider-gateway POST /v1/tts."""
    url = f"{config.provider_gateway_url.rstrip('/')}/v1/tts"
    payload = {"text": text, "voice": voice, "speed": speed}
    logger.info("voice synthesize_speech → %s chars=%d", url, len(text))
    async with httpx.AsyncClient(timeout=httpx.Timeout(config.timeout_seconds, connect=10.0)) as http:
        response = await http.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
    # Normalize
    if "duration_seconds" not in data:
        data["duration_seconds"] = max(1.0, len(text) / 15.0)
    if "word_timings" not in data or not data["word_timings"]:
        # Derive simple timings if mock omits them
        words = text.split()
        t = 0.0
        timings = []
        for w in words:
            dur = max(0.15, len(w) / 12.0)
            timings.append({"word": w, "start": round(t, 3), "end": round(t + dur, 3)})
            t += dur
        data["word_timings"] = timings
        data["duration_seconds"] = round(t, 3)
    return data


async def plan_delivery(
    script: dict[str, Any],
    *,
    voice_profile: str,
    language: str,
    pacing: str,
    config: VoiceAgentConfig,
) -> LLMResponse:
    """Optional LLM planning for emotion/emphasis (uses /v1/complete)."""
    context = {
        "script": script,
        "voice_profile": voice_profile,
        "language": language,
        "pacing": pacing,
        "target_platform": "youtube",
    }
    prompt = render_synthesize_prompt(context)
    prompt += (
        f"\n\n## Script payload\n{json.dumps(script)[:3000]}\n"
        f"Voice profile: {voice_profile}\nPacing: {pacing}\nLanguage: {language}\n"
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
    async with httpx.AsyncClient(timeout=httpx.Timeout(llm_cfg.timeout_seconds, connect=10.0)) as http:
        response = await http.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
    text = data.get("text") or data.get("content") or ""
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
