"""Runway ML adapter for text-to-video and image-to-video generation."""

from __future__ import annotations

import logging
from typing import Any

from provider_gateway.adapters.base import BaseProviderAdapter, ProviderCapability
from provider_gateway.config import ProviderConfig

logger = logging.getLogger(__name__)


class RunwayAdapter(BaseProviderAdapter[dict[str, Any]]):
    """Runway Gen-3 Alpha adapter for cinematic video generation."""

    MODELS = [
        {"model_id": "gen3a_turbo", "name": "Gen-3 Alpha Turbo", "capabilities": ["video_generate"]},
        {"model_id": "gen3a", "name": "Gen-3 Alpha", "capabilities": ["video_generate"]},
        {"model_id": "gen2", "name": "Gen-2", "capabilities": ["video_generate"]},
    ]

    # Pricing per second of generated video
    PRICING = {
        "gen3a_turbo": 0.50,
        "gen3a": 1.00,
        "gen2": 0.25,
    }

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._client: Any = None
        self._base_url = config.base_url or "https://api.runwayml.com/v1"
        try:
            import httpx
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={"Authorization": f"Bearer {config.api_key}"},
                timeout=config.timeout_seconds,
            )
        except ImportError:
            logger.warning("httpx not installed; Runway adapter in mock mode")

    @property
    def provider_id(self) -> str:
        return "runway"

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
        model = request.get("model", "gen3a_turbo")
        duration = request.get("duration_seconds", 5)
        resolution = request.get("resolution", "1080p")
        image_url = request.get("image_url")

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "duration": duration,
            "ratio": "16:9" if resolution in ("1080p", "720p") else "9:16",
        }
        if image_url:
            payload["image_url"] = image_url
            endpoint = "/image_to_video"
        else:
            endpoint = "/text_to_video"

        resp = await self._client.post(endpoint, json=payload)
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
        model = request.get("model", "gen3a_turbo")
        duration = request.get("duration_seconds", 5)
        resolution = request.get("resolution", "1080p")
        return {
            "video_url": f"https://cdn.sentra-aura.dev/videos/runway/{hash(prompt) % 1000000}.mp4",
            "provider": self.provider_id,
            "model": model,
            "duration_seconds": duration,
            "resolution": resolution,
            "job_id": f"runway-{hash(prompt) % 1000000}",
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
        model = request.get("model", "gen3a_turbo")
        duration = request.get("duration_seconds", 5)
        rate = self.PRICING.get(model, 0.50)
        return round(duration * rate, 6)
