"""Google Gemini adapter via Generative Language API."""

from __future__ import annotations

import logging
from typing import Any

from provider_gateway.adapters.base import BaseProviderAdapter, ProviderCapability
from provider_gateway.config import ProviderConfig

logger = logging.getLogger(__name__)


class GoogleAdapter(BaseProviderAdapter[dict[str, Any]]):
    """Google Gemini adapter with multimodal input support."""

    MODELS = [
        {"model_id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "capabilities": ["llm_complete", "llm_stream"]},
        {"model_id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "capabilities": ["llm_complete"]},
        {"model_id": "gemini-1.0-pro", "name": "Gemini 1.0 Pro", "capabilities": ["llm_complete"]},
        {"model_id": "text-embedding-004", "name": "Text Embedding 004", "capabilities": ["embed"]},
    ]

    PRICING = {
        "gemini-1.5-pro": {"input": 3.5, "output": 10.5},
        "gemini-1.5-flash": {"input": 0.35, "output": 0.70},
        "gemini-1.0-pro": {"input": 0.50, "output": 1.50},
        "text-embedding-004": {"input": 0.10, "output": 0.0},
    }

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._client: Any = None
        try:
            import google.generativeai as genai
            genai.configure(api_key=config.api_key)
            self._client = genai
        except ImportError:
            logger.warning("google-generativeai not installed; Google adapter in mock mode")

    @property
    def provider_id(self) -> str:
        return "google"

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
        model_name = request.get("model", "gemini-1.5-pro")
        temperature = request.get("temperature", 0.7)
        max_tokens = request.get("max_tokens", 1024)

        if "embedding" in model_name or request.get("capability") == ProviderCapability.EMBED.value:
            model = self._client.GenerativeModel(model_name)
            result = model.embed_content(content=request.get("text", prompt))
            return {
                "embedding": result.embedding if hasattr(result, "embedding") else [],
                "model": model_name,
                "prompt_tokens": len(request.get("text", prompt).split()),
            }

        model = self._client.GenerativeModel(model_name)
        generation_config = self._client.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        response = model.generate_content(prompt, generation_config=generation_config)
        text = response.text if hasattr(response, "text") else ""
        usage = response.usage_metadata if hasattr(response, "usage_metadata") else None

        return {
            "text": text,
            "model": model_name,
            "prompt_tokens": usage.prompt_token_count if usage else len(prompt.split()),
            "completion_tokens": usage.candidates_token_count if usage else 20,
            "total_tokens": usage.total_token_count if usage else len(prompt.split()) + 20,
            "finish_reason": "stop",
        }

    def _mock_execute(self, request: dict[str, Any]) -> dict[str, Any]:
        prompt = request.get("prompt", "")
        model = request.get("model", "gemini-1.5-pro")
        if "embedding" in model:
            dim = request.get("dimensions", 768)
            return {
                "embedding": [0.002] * dim,
                "model": model,
                "prompt_tokens": len(request.get("text", prompt).split()),
            }
        return {
            "text": f"[MOCK Google response to: {prompt[:80]}...]",
            "model": model,
            "prompt_tokens": len(prompt.split()),
            "completion_tokens": 22,
            "total_tokens": len(prompt.split()) + 22,
            "finish_reason": "stop",
        }

    async def _health_check_impl(self) -> bool:
        if self._client is None:
            return True
        try:
            models = self._client.list_models()
            return len(list(models)) > 0
        except Exception:
            return False

    def estimate_cost(self, request: dict[str, Any]) -> float:
        model = request.get("model", "gemini-1.5-pro")
        pricing = self.PRICING.get(model, {"input": 3.5, "output": 10.5})
        if "embedding" in model:
            tokens = len(request.get("text", request.get("prompt", "")).split())
            return round((tokens / 1_000_000) * pricing["input"], 6)
        prompt_tokens = len(request.get("prompt", "").split())
        max_tokens = request.get("max_tokens", 1024)
        input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (max_tokens / 1_000_000) * pricing["output"]
        return round(input_cost + output_cost, 6)
