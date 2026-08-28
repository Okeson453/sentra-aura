"""Stability AI Stable Diffusion adapter with style presets and negative prompts."""

from __future__ import annotations

import logging
from typing import Any

from provider_gateway.adapters.base import BaseProviderAdapter, ProviderCapability
from provider_gateway.config import ProviderConfig

logger = logging.getLogger(__name__)


class StableDiffusionAdapter(BaseProviderAdapter[dict[str, Any]]):
    """Stability AI Stable Diffusion 3 and SDXL adapter."""

    MODELS = [
        {"model_id": "stable-diffusion-v3-medium", "name": "SD3 Medium", "capabilities": ["image_generate"]},
        {"model_id": "stable-diffusion-xl-1024-v1-0", "name": "SDXL 1.0", "capabilities": ["image_generate"]},
        {"model_id": "stable-diffusion-512-v2-1", "name": "SD 2.1", "capabilities": ["image_generate"]},
    ]

    # Pricing per image (credits-based, approximated to USD)
    PRICING = {
        "stable-diffusion-v3-medium": 0.035,
        "stable-diffusion-xl-1024-v1-0": 0.02,
        "stable-diffusion-512-v2-1": 0.01,
    }

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._client: Any = None
        self._base_url = config.base_url or "https://api.stability.ai/v2beta"
        try:
            import httpx
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={"Authorization": f"Bearer {config.api_key}"},
                timeout=config.timeout_seconds,
            )
        except ImportError:
            logger.warning("httpx not installed; Stable Diffusion adapter in mock mode")

    @property
    def provider_id(self) -> str:
        return "stablediffusion"

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
        model = request.get("model", "stable-diffusion-v3-medium")
        size = request.get("size", "1024x1024")
        style = request.get("style", "photographic")
        negative_prompt = request.get("negative_prompt", "")

        width, height = map(int, size.split("x"))
        endpoint = "/stable-image/generate/sd3" if "v3" in model else "/stable-image/generate/core"

        payload = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "style_preset": style,
            "negative_prompt": negative_prompt,
            "model": model,
        }

        resp = await self._client.post(endpoint, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return {
            "image_url": data.get("image_url", ""),
            "provider": self.provider_id,
            "model": model,
            "resolution": size,
            "seed": data.get("seed"),
        }

    def _mock_execute(self, request: dict[str, Any]) -> dict[str, Any]:
        prompt = request.get("prompt", "")
        model = request.get("model", "stable-diffusion-v3-medium")
        size = request.get("size", "1024x1024")
        return {
            "image_url": f"https://cdn.sentra-aura.dev/images/stablediffusion/{hash(prompt) % 1000000}.png",
            "provider": self.provider_id,
            "model": model,
            "resolution": size,
            "seed": hash(prompt) % 1000000,
        }

    async def _health_check_impl(self) -> bool:
        if self._client is None:
            return True
        try:
            resp = await self._client.get("/user/balance")
            return resp.status_code == 200
        except Exception:
            return False

    def estimate_cost(self, request: dict[str, Any]) -> float:
        model = request.get("model", "stable-diffusion-v3-medium")
        return round(self.PRICING.get(model, 0.035), 6)
