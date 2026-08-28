"""Pika Labs adapter for AI video generation with motion control."""

from __future__ import annotations

import logging
from typing import Any

from provider_gateway.adapters.base import BaseProviderAdapter, ProviderCapability
from provider_gateway.config import ProviderConfig

logger = logging.getLogger(__name__)


class PikaAdapter(BaseProviderAdapter[dict[str, Any]]):
    """Pika 1.5 adapter for stylized video generation."""

    MODELS = [
        {"model_id": "pika-1.5", "name": "Pika 1.5", "capabilities": ["video_generate"]},
        {"model_id": "pika-1.0", "name": "Pika 1.0", "capabilities": ["video_generate"]},
    ]

    # Pricing per second
    PRICING = {
        "pika-1.5": 0.40,
        "pika-1.0": 0.30,
    }

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._client: Any = None
        self._base_url = config.base_url or "https://api.pika.art/v1"
        try:
            import httpx
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={"Authorization": f"Bearer {config.api_key}"},
                timeout=config.timeout_seconds,
            )
        except ImportError:
            logger.warning("httpx not installed; Pika adapter in mock mode")

    @property
    def provider_id(self) -> str:
        return "pika"

    @property
    def capabilities(self) -> list[ProviderCapability]:
        return [ProviderCapability.VIDEO_GENERATE]

    @property
    def models(self) -> list[dict[str, Any]]:
        return self.MODELS

    async def _execute(self, request: dict[str, Any]) -> dict[str, Any]:
        if self._client is None:
            return self._mock_execute(request)

        prompt = request.get("prompt", "")
        model = request.get("model", "pika-1.5")
        duration = request.get("duration_seconds", 5)
        resolution = request.get("resolution", "1080p")
        negative_prompt = request.get("negative_prompt", "")
        image_url = request.get("image_url")

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "duration": duration,
            "aspect_ratio": "16:9" if resolution in ("1080p", "720p") else "9:16",
            "negative_prompt": negative_prompt,
        }
        if image_url:
            payload["image_url"] = image_url

        resp = await self._client.post("/generate", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return {
            "video_url": data.get("video_url", ""),
            "provider": self.provider_id,
            "model": model,
            "duration_seconds": duration,
            "resolution": resolution,
            "job_id": data.get("id"),
        }

    def _mock_execute(self, request: dict[str, Any]) -> dict[str, Any]:
        prompt = request.get("prompt", "")
        model = request.get("model", "pika-1.5")
        duration = request.get("duration_seconds", 5)
        resolution = request.get("resolution", "1080p")
        return {
            "video_url": f"https://cdn.sentra-aura.dev/videos/pika/{hash(prompt) % 1000000}.mp4",
            "provider": self.provider_id,
            "model": model,
            "duration_seconds": duration,
            "resolution": resolution,
            "job_id": f"pika-{hash(prompt) % 1000000}",
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
        model = request.get("model", "pika-1.5")
        duration = request.get("duration_seconds", 5)
        rate = self.PRICING.get(model, 0.40)
        return round(duration * rate, 6)
