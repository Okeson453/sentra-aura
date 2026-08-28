"""Midjourney adapter via Imagine API with style and aspect ratio control."""

from __future__ import annotations

import logging
from typing import Any

from provider_gateway.adapters.base import BaseProviderAdapter, ProviderCapability
from provider_gateway.config import ProviderConfig

logger = logging.getLogger(__name__)


class MidjourneyAdapter(BaseProviderAdapter[dict[str, Any]]):
    """Midjourney adapter using the Imagine API (third-party bridge)."""

    MODELS = [
        {"model_id": "midjourney-v6", "name": "Midjourney v6", "capabilities": ["image_generate"]},
        {"model_id": "midjourney-v5.2", "name": "Midjourney v5.2", "capabilities": ["image_generate"]},
        {"model_id": "niji-6", "name": "Niji v6", "capabilities": ["image_generate"]},
    ]

    # Pricing per image job
    PRICING = {
        "midjourney-v6": 0.10,
        "midjourney-v5.2": 0.08,
        "niji-6": 0.10,
    }

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._client: Any = None
        self._base_url = config.base_url or "https://api.midjourney.com/v1"
        try:
            import httpx
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={"Authorization": f"Bearer {config.api_key}"},
                timeout=config.timeout_seconds,
            )
        except ImportError:
            logger.warning("httpx not installed; Midjourney adapter in mock mode")

    @property
    def provider_id(self) -> str:
        return "midjourney"

    @property
    def capabilities(self) -> list[ProviderCapability]:
        return [ProviderCapability.IMAGE_GENERATE]

    @property
    def models(self) -> list[dict[str, Any]]:
        return self.MODELS

    async def _execute(self, request: dict[str, Any]) -> dict[str, Any]:
        if self._client is None:
            return self._mock_execute(request)

        prompt = request.get("prompt", "")
        model = request.get("model", "midjourney-v6")
        size = request.get("size", "1024x1024")
        style = request.get("style", "raw")

        # Map size to aspect ratio
        ar_map = {"1024x1024": "1:1", "1024x1792": "9:16", "1792x1024": "16:9"}
        aspect_ratio = ar_map.get(size, "1:1")

        resp = await self._client.post("/imagine", json={
            "prompt": prompt,
            "version": model,
            "aspect_ratio": aspect_ratio,
            "style": style,
        })
        resp.raise_for_status()
        data = resp.json()
        return {
            "image_url": data.get("image_url", ""),
            "provider": self.provider_id,
            "model": model,
            "resolution": size,
            "job_id": data.get("job_id"),
        }

    def _mock_execute(self, request: dict[str, Any]) -> dict[str, Any]:
        prompt = request.get("prompt", "")
        model = request.get("model", "midjourney-v6")
        size = request.get("size", "1024x1024")
        return {
            "image_url": f"https://cdn.sentra-aura.dev/images/midjourney/{hash(prompt) % 1000000}.png",
            "provider": self.provider_id,
            "model": model,
            "resolution": size,
            "job_id": f"mj-{hash(prompt) % 1000000}",
        }

    async def _health_check_impl(self) -> bool:
        if self._client is None:
            return True
        try:
            resp = await self._client.get("/health")
            return resp.status_code == 200
        except Exception:
            return False

    def estimate_cost(self, request: dict[str, Any]) -> float:
        model = request.get("model", "midjourney-v6")
        return round(self.PRICING.get(model, 0.10), 6)
