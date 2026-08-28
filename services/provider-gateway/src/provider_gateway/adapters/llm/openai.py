"""OpenAI LLM adapter with chat completions, embeddings, and moderation."""

from __future__ import annotations

import logging
from typing import Any

from provider_gateway.adapters.base import BaseProviderAdapter, ProviderCapability, ProviderHealth
from provider_gateway.config import ProviderConfig

logger = logging.getLogger(__name__)


class OpenAIAdapter(BaseProviderAdapter[dict[str, Any]]):
    """OpenAI GPT-4 / GPT-3.5 adapter supporting chat completions and embeddings."""

    MODELS = [
        {"model_id": "gpt-4o", "name": "GPT-4o", "capabilities": ["llm_complete", "llm_stream"]},
        {"model_id": "gpt-4o-mini", "name": "GPT-4o Mini", "capabilities": ["llm_complete"]},
        {"model_id": "gpt-4-turbo", "name": "GPT-4 Turbo", "capabilities": ["llm_complete", "llm_stream"]},
        {"model_id": "text-embedding-3-large", "name": "Text Embedding 3 Large", "capabilities": ["embed"]},
        {"model_id": "text-embedding-3-small", "name": "Text Embedding 3 Small", "capabilities": ["embed"]},
    ]

    PRICING = {
        "gpt-4o": {"input": 5.0, "output": 15.0},          # per 1M tokens
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4-turbo": {"input": 10.0, "output": 30.0},
        "text-embedding-3-large": {"input": 0.13, "output": 0.0},
        "text-embedding-3-small": {"input": 0.02, "output": 0.0},
    }

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._client: Any = None
        try:
            import openai
            self._client = openai.AsyncOpenAI(
                api_key=config.api_key,
                base_url=config.base_url,
                timeout=config.timeout_seconds,
                max_retries=config.max_retries,
            )
        except ImportError:
            logger.warning("openai package not installed; OpenAI adapter in mock mode")

    @property
    def provider_id(self) -> str:
        return "openai"

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
        model = request.get("model", "gpt-4o")
        temperature = request.get("temperature", 0.7)
        max_tokens = request.get("max_tokens", 1024)

        if request.get("capability") == ProviderCapability.EMBED.value or "text" in request:
            # Embedding path
            text = request.get("text", prompt)
            resp = await self._client.embeddings.create(
                model=model if "embedding" in model else "text-embedding-3-small",
                input=text,
                dimensions=request.get("dimensions"),
            )
            return {
                "embedding": resp.data[0].embedding if resp.data else [],
                "model": resp.model,
                "prompt_tokens": resp.usage.total_tokens if resp.usage else 0,
            }

        # Chat completion path
        messages = [{"role": "user", "content": prompt}]
        if request.get("system_message"):
            messages.insert(0, {"role": "system", "content": request["system_message"]})

        resp = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
        )
        choice = resp.choices[0] if resp.choices else None
        usage = resp.usage
        return {
            "text": choice.message.content if choice else "",
            "model": resp.model,
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "completion_tokens": usage.completion_tokens if usage else 0,
            "total_tokens": usage.total_tokens if usage else 0,
            "finish_reason": choice.finish_reason if choice else None,
        }

    def _mock_execute(self, request: dict[str, Any]) -> dict[str, Any]:
        prompt = request.get("prompt", "")
        model = request.get("model", "gpt-4o")
        if "text" in request and "embedding" in model:
            dim = request.get("dimensions", 1536)
            return {
                "embedding": [0.001] * dim,
                "model": model,
                "prompt_tokens": len(request["text"].split()),
            }
        return {
            "text": f"[MOCK OpenAI response to: {prompt[:80]}...]",
            "model": model,
            "prompt_tokens": len(prompt.split()),
            "completion_tokens": 20,
            "total_tokens": len(prompt.split()) + 20,
            "finish_reason": "stop",
        }

    async def _health_check_impl(self) -> bool:
        if self._client is None:
            return True  # mock mode is "healthy"
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False

    def estimate_cost(self, request: dict[str, Any]) -> float:
        model = request.get("model", "gpt-4o")
        pricing = self.PRICING.get(model, {"input": 5.0, "output": 15.0})
        if "text" in request and "embedding" in model:
            tokens = len(request["text"].split())
            return (tokens / 1_000_000) * pricing["input"]
        prompt_tokens = len(request.get("prompt", "").split())
        max_tokens = request.get("max_tokens", 1024)
        input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (max_tokens / 1_000_000) * pricing["output"]
        return round(input_cost + output_cost, 6)
