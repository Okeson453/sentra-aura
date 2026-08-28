"""Anthropic Claude adapter with Messages API and tool-use support."""

from __future__ import annotations

import logging
from typing import Any

from provider_gateway.adapters.base import BaseProviderAdapter, ProviderCapability
from provider_gateway.config import ProviderConfig

logger = logging.getLogger(__name__)


class AnthropicAdapter(BaseProviderAdapter[dict[str, Any]]):
    """Anthropic Claude adapter using the Messages API."""

    MODELS = [
        {"model_id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "capabilities": ["llm_complete", "llm_stream"]},
        {"model_id": "claude-3-opus-20240229", "name": "Claude 3 Opus", "capabilities": ["llm_complete"]},
        {"model_id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku", "capabilities": ["llm_complete"]},
    ]

    PRICING = {
        "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
        "claude-3-opus-20240229": {"input": 15.0, "output": 75.0},
        "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    }

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._client: Any = None
        try:
            import anthropic
            self._client = anthropic.AsyncAnthropic(
                api_key=config.api_key,
                base_url=config.base_url,
                timeout=config.timeout_seconds,
                max_retries=config.max_retries,
            )
        except ImportError:
            logger.warning("anthropic package not installed; Anthropic adapter in mock mode")

    @property
    def provider_id(self) -> str:
        return "anthropic"

    @property
    def capabilities(self) -> list[ProviderCapability]:
        return [ProviderCapability.LLM_COMPLETE, ProviderCapability.LLM_STREAM]

    @property
    def models(self) -> list[dict[str, Any]]:
        return self.MODELS

    async def _execute(self, request: dict[str, Any]) -> dict[str, Any]:
        if self._client is None:
            return self._mock_execute(request)

        prompt = request.get("prompt", "")
        model = request.get("model", "claude-3-5-sonnet-20241022")
        max_tokens = request.get("max_tokens", 1024)
        temperature = request.get("temperature", 0.7)
        system = request.get("system_message", "")

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        resp = await self._client.messages.create(**kwargs)
        content = ""
        for block in resp.content:
            if block.type == "text":
                content += block.text

        return {
            "text": content,
            "model": resp.model,
            "prompt_tokens": resp.usage.input_tokens if resp.usage else 0,
            "completion_tokens": resp.usage.output_tokens if resp.usage else 0,
            "total_tokens": (resp.usage.input_tokens + resp.usage.output_tokens) if resp.usage else 0,
            "finish_reason": resp.stop_reason,
        }

    def _mock_execute(self, request: dict[str, Any]) -> dict[str, Any]:
        prompt = request.get("prompt", "")
        model = request.get("model", "claude-3-5-sonnet-20241022")
        return {
            "text": f"[MOCK Anthropic response to: {prompt[:80]}...]",
            "model": model,
            "prompt_tokens": len(prompt.split()),
            "completion_tokens": 25,
            "total_tokens": len(prompt.split()) + 25,
            "finish_reason": "end_turn",
        }

    async def _health_check_impl(self) -> bool:
        if self._client is None:
            return True
        try:
            # Anthropic does not have a lightweight models.list; use a tiny completion
            await self._client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}],
            )
            return True
        except Exception:
            return False

    def estimate_cost(self, request: dict[str, Any]) -> float:
        model = request.get("model", "claude-3-5-sonnet-20241022")
        pricing = self.PRICING.get(model, {"input": 3.0, "output": 15.0})
        prompt_tokens = len(request.get("prompt", "").split())
        max_tokens = request.get("max_tokens", 1024)
        input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (max_tokens / 1_000_000) * pricing["output"]
        return round(input_cost + output_cost, 6)
