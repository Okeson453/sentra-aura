"""Cohere Command-R adapter with RAG-native generation and embeddings."""

from __future__ import annotations

import logging
from typing import Any

from provider_gateway.adapters.base import BaseProviderAdapter, ProviderCapability
from provider_gateway.config import ProviderConfig

logger = logging.getLogger(__name__)


class CohereAdapter(BaseProviderAdapter[dict[str, Any]]):
    """Cohere Command-R adapter optimized for RAG and tool use."""

    MODELS = [
        {"model_id": "command-r-plus", "name": "Command R+", "capabilities": ["llm_complete"]},
        {"model_id": "command-r", "name": "Command R", "capabilities": ["llm_complete"]},
        {"model_id": "command", "name": "Command", "capabilities": ["llm_complete"]},
        {"model_id": "embed-english-v3.0", "name": "Embed English v3", "capabilities": ["embed"]},
        {"model_id": "embed-multilingual-v3.0", "name": "Embed Multilingual v3", "capabilities": ["embed"]},
    ]

    PRICING = {
        "command-r-plus": {"input": 3.0, "output": 15.0},
        "command-r": {"input": 0.50, "output": 1.50},
        "command": {"input": 1.0, "output": 2.0},
        "embed-english-v3.0": {"input": 0.10, "output": 0.0},
        "embed-multilingual-v3.0": {"input": 0.10, "output": 0.0},
    }

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._client: Any = None
        try:
            import cohere
            self._client = cohere.AsyncClientV2(
                api_key=config.api_key,
                base_url=config.base_url,
                timeout=config.timeout_seconds,
            )
        except ImportError:
            logger.warning("cohere package not installed; Cohere adapter in mock mode")

    @property
    def provider_id(self) -> str:
        return "cohere"

    @property
    def capabilities(self) -> list[ProviderCapability]:
        return [ProviderCapability.LLM_COMPLETE, ProviderCapability.EMBED]

    @property
    def models(self) -> list[dict[str, Any]]:
        return self.MODELS

    async def _execute(self, request: dict[str, Any]) -> dict[str, Any]:
        if self._client is None:
            return self._mock_execute(request)

        prompt = request.get("prompt", "")
        model = request.get("model", "command-r")

        if "embed" in model or request.get("capability") == ProviderCapability.EMBED.value:
            resp = await self._client.embed(
                model=model,
                texts=[request.get("text", prompt)],
                input_type="search_document",
            )
            return {
                "embedding": resp.embeddings[0] if resp.embeddings else [],
                "model": model,
                "prompt_tokens": len(request.get("text", prompt).split()),
            }

        messages = [{"role": "user", "content": prompt}]
        if request.get("system_message"):
            messages.insert(0, {"role": "system", "content": request["system_message"]})

        resp = await self._client.chat(
            model=model,
            messages=messages,
            temperature=request.get("temperature", 0.7),
            max_tokens=request.get("max_tokens", 1024),
        )
        content = ""
        if resp.message and resp.message.content:
            for block in resp.message.content:
                if block.type == "text":
                    content += block.text

        usage = resp.usage
        return {
            "text": content,
            "model": model,
            "prompt_tokens": usage.tokens.input_tokens if usage else len(prompt.split()),
            "completion_tokens": usage.tokens.output_tokens if usage else 20,
            "total_tokens": usage.tokens.total_tokens if usage else len(prompt.split()) + 20,
            "finish_reason": "complete",
        }

    def _mock_execute(self, request: dict[str, Any]) -> dict[str, Any]:
        prompt = request.get("prompt", "")
        model = request.get("model", "command-r")
        if "embed" in model:
            dim = request.get("dimensions", 1024)
            return {
                "embedding": [0.003] * dim,
                "model": model,
                "prompt_tokens": len(request.get("text", prompt).split()),
            }
        return {
            "text": f"[MOCK Cohere response to: {prompt[:80]}...]",
            "model": model,
            "prompt_tokens": len(prompt.split()),
            "completion_tokens": 18,
            "total_tokens": len(prompt.split()) + 18,
            "finish_reason": "complete",
        }

    async def _health_check_impl(self) -> bool:
        if self._client is None:
            return True
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False

    def estimate_cost(self, request: dict[str, Any]) -> float:
        model = request.get("model", "command-r")
        pricing = self.PRICING.get(model, {"input": 0.50, "output": 1.50})
        if "embed" in model:
            tokens = len(request.get("text", request.get("prompt", "")).split())
            return round((tokens / 1_000_000) * pricing["input"], 6)
        prompt_tokens = len(request.get("prompt", "").split())
        max_tokens = request.get("max_tokens", 1024)
        input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (max_tokens / 1_000_000) * pricing["output"]
        return round(input_cost + output_cost, 6)
