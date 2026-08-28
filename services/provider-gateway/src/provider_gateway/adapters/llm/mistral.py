"""Mistral AI adapter with Mixtral and Codestral model support."""

from __future__ import annotations

import logging
from typing import Any

from provider_gateway.adapters.base import BaseProviderAdapter, ProviderCapability
from provider_gateway.config import ProviderConfig

logger = logging.getLogger(__name__)


class MistralAdapter(BaseProviderAdapter[dict[str, Any]]):
    """Mistral AI adapter supporting Mixtral, Mistral Large, and Codestral."""

    MODELS = [
        {"model_id": "mistral-large-latest", "name": "Mistral Large", "capabilities": ["llm_complete", "llm_stream"]},
        {"model_id": "mistral-medium-latest", "name": "Mistral Medium", "capabilities": ["llm_complete"]},
        {"model_id": "codestral-latest", "name": "Codestral", "capabilities": ["llm_complete"]},
        {"model_id": "mistral-embed", "name": "Mistral Embed", "capabilities": ["embed"]},
    ]

    PRICING = {
        "mistral-large-latest": {"input": 2.0, "output": 6.0},
        "mistral-medium-latest": {"input": 0.90, "output": 2.70},
        "codestral-latest": {"input": 1.0, "output": 3.0},
        "mistral-embed": {"input": 0.10, "output": 0.0},
    }

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._client: Any = None
        try:
            from mistralai import Mistral
            self._client = Mistral(
                api_key=config.api_key,
            )
        except ImportError:
            logger.warning("mistralai package not installed; Mistral adapter in mock mode")

    @property
    def provider_id(self) -> str:
        return "mistral"

    @property
    def capabilities(self) -> list[ProviderCapability]:
        return [ProviderCapability.LLM_COMPLETE, ProviderCapability.LLM_STREAM, ProviderCapability.EMBED]

    @property
    def models(self) -> list[dict[str, Any]]:
        return self.MODELS

    async def _execute(self, request: dict[str, Any]) -> dict[str, Any]:
        if self._client is None:
            return self._mock_execute(request)

        prompt = request.get("prompt", "")
        model = request.get("model", "mistral-large-latest")

        if "embed" in model or request.get("capability") == ProviderCapability.EMBED.value:
            resp = await self._client.embeddings.create_async(
                model=model,
                inputs=[request.get("text", prompt)],
            )
            return {
                "embedding": resp.data[0].embedding if resp.data else [],
                "model": model,
                "prompt_tokens": len(request.get("text", prompt).split()),
            }

        messages = [{"role": "user", "content": prompt}]
        if request.get("system_message"):
            messages.insert(0, {"role": "system", "content": request["system_message"]})

        resp = await self._client.chat.complete_async(
            model=model,
            messages=messages,
            temperature=request.get("temperature", 0.7),
            max_tokens=request.get("max_tokens", 1024),
        )
        choice = resp.choices[0] if resp.choices else None
        usage = resp.usage
        return {
            "text": choice.message.content if choice else "",
            "model": model,
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "completion_tokens": usage.completion_tokens if usage else 0,
            "total_tokens": usage.total_tokens if usage else 0,
            "finish_reason": choice.finish_reason if choice else None,
        }

    def _mock_execute(self, request: dict[str, Any]) -> dict[str, Any]:
        prompt = request.get("prompt", "")
        model = request.get("model", "mistral-large-latest")
        if "embed" in model:
            dim = request.get("dimensions", 1024)
            return {
                "embedding": [0.004] * dim,
                "model": model,
                "prompt_tokens": len(request.get("text", prompt).split()),
            }
        return {
            "text": f"[MOCK Mistral response to: {prompt[:80]}...]",
            "model": model,
            "prompt_tokens": len(prompt.split()),
            "completion_tokens": 19,
            "total_tokens": len(prompt.split()) + 19,
            "finish_reason": "stop",
        }

    async def _health_check_impl(self) -> bool:
        if self._client is None:
            return True
        try:
            await self._client.models.list_async()
            return True
        except Exception:
            return False

    def estimate_cost(self, request: dict[str, Any]) -> float:
        model = request.get("model", "mistral-large-latest")
        pricing = self.PRICING.get(model, {"input": 2.0, "output": 6.0})
        if "embed" in model:
            tokens = len(request.get("text", request.get("prompt", "")).split())
            return round((tokens / 1_000_000) * pricing["input"], 6)
        prompt_tokens = len(request.get("prompt", "").split())
        max_tokens = request.get("max_tokens", 1024)
        input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (max_tokens / 1_000_000) * pricing["output"]
        return round(input_cost + output_cost, 6)
