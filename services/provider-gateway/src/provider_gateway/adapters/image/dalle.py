"""OpenAI DALL-E adapter for image generation and editing."""

from __future__ import annotations

import logging
from typing import Any

from provider_gateway.adapters.base import BaseProviderAdapter, ProviderCapability
from provider_gateway.config import ProviderConfig

logger = logging.getLogger(__name__)


class DALLEAdapter(BaseProviderAdapter[dict[str, Any]]):
    """OpenAI DALL-E 3 and DALL-E 2 image generation adapter."""

    MODELS = [
        {"model_id": "dall-e-3", "name": "DALL-E 3", "capabilities": ["image_generate"]},
        {"model_id": "dall-e-2", "name": "DALL-E 2", "capabilities": ["image_generate", "image_edit"]},
    ]

    # Pricing per image
    PRICING = {
        "dall-e-3": {"1024x1024": 0.04, "1024x1792": 0.08, "1792x1024": 0.08},
        "dall-e-2": {"1024x1024": 0.02, "512x512": 0.018, "256x256": 0.016},
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
            logger.warning("openai package not installed; DALL-E adapter in mock mode")

    @property
    def provider_id(self) -> str:
        return "dalle"

    @property
    def capabilities(self) -> list[ProviderCapability]:
        return [ProviderCapability.IMAGE_GENERATE, ProviderCapability.IMAGE_EDIT]

    @property
    def models(self) -> list[dict[str, Any]]:
        return self.MODELS

    async def _execute(self, request: dict[str, Any]) -> dict[str, Any]:
        if self._client is None:
            return self._mock_execute(request)

        prompt = request.get("prompt", "")
        model = request.get("model", "dall-e-3")
        size = request.get("size", "1024x1024")
        style = request.get("style", "vivid")
        quality = request.get("quality", "standard")

        resp = await self._client.images.generate(
            model=model,
            prompt=prompt,
            size=size,
            style=style if model == "dall-e-3" else None,
            quality=quality if model == "dall-e-3" else None,
            n=1,
        )
        image_url = resp.data[0].url if resp.data else ""
        return {
            "image_url": image_url,
            "provider": self.provider_id,
            "model": model,
            "resolution": size,
            "revised_prompt": resp.data[0].revised_prompt if resp.data and hasattr(resp.data[0], "revised_prompt") else None,
        }

    def _mock_execute(self, request: dict[str, Any]) -> dict[str, Any]:
        prompt = request.get("prompt", "")
        model = request.get("model", "dall-e-3")
        size = request.get("size", "1024x1024")
        return {
            "image_url": f"https://cdn.sentra-aura.dev/images/dalle/{hash(prompt) % 1000000}.png",
            "provider": self.provider_id,
            "model": model,
            "resolution": size,
            "revised_prompt": None,
        }

    async def _health_check_impl(self) -> bool:
        if self._client is None:
            return True
        try:
            # Reuse the OpenAI client models list
            await self._client.models.list()
            return True
        except Exception:
            return False

    def estimate_cost(self, request: dict[str, Any]) -> float:
        model = request.get("model", "dall-e-3")
        size = request.get("size", "1024x1024")
        pricing = self.PRICING.get(model, {})
        return round(pricing.get(size, 0.04), 6)
