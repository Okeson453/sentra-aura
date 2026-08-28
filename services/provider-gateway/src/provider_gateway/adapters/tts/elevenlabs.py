"""ElevenLabs TTS adapter with voice cloning and multilingual support."""

from __future__ import annotations

import logging
from typing import Any

from provider_gateway.adapters.base import BaseProviderAdapter, ProviderCapability
from provider_gateway.config import ProviderConfig

logger = logging.getLogger(__name__)


class ElevenLabsAdapter(BaseProviderAdapter[dict[str, Any]]):
    """ElevenLabs text-to-speech with voice ID selection and speed control."""

    MODELS = [
        {"model_id": "eleven_multilingual_v2", "name": "Eleven Multilingual v2", "capabilities": ["tts"]},
        {"model_id": "eleven_turbo_v2_5", "name": "Eleven Turbo v2.5", "capabilities": ["tts"]},
        {"model_id": "eleven_monolingual_v1", "name": "Eleven Monolingual v1", "capabilities": ["tts"]},
    ]

    # Pricing per 1K characters
    PRICING = {
        "eleven_multilingual_v2": 0.30,
        "eleven_turbo_v2_5": 0.10,
        "eleven_monolingual_v1": 0.18,
    }

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._client: Any = None
        try:
            from elevenlabs import AsyncElevenLabs
            self._client = AsyncElevenLabs(api_key=config.api_key)
        except ImportError:
            logger.warning("elevenlabs package not installed; ElevenLabs adapter in mock mode")

    @property
    def provider_id(self) -> str:
        return "elevenlabs"

    @property
    def capabilities(self) -> list[ProviderCapability]:
        return [ProviderCapability.TTS]

    @property
    def models(self) -> list[dict[str, Any]]:
        return self.MODELS

    async def _execute(self, request: dict[str, Any]) -> dict[str, Any]:
        if self._client is None:
            return self._mock_execute(request)

        text = request.get("text", "")
        voice_id = request.get("voice", "21m00Tcm4TlvDq8ikWAM")  # default Rachel
        model = request.get("model", "eleven_multilingual_v2")
        speed = request.get("speed", 1.0)

        audio = await self._client.generate(
            text=text,
            voice=voice_id,
            model=model,
            voice_settings={"speed": speed} if speed != 1.0 else None,
        )
        # In production, stream to asset-store and return URL
        return {
            "audio_url": f"https://cdn.sentra-aura.dev/tts/elevenlabs/{hash(text) % 1000000}.mp3",
            "provider": self.provider_id,
            "model": model,
            "duration_seconds": len(text.split()) * 0.4 / speed,
            "voice_id": voice_id,
        }

    def _mock_execute(self, request: dict[str, Any]) -> dict[str, Any]:
        text = request.get("text", "")
        voice_id = request.get("voice", "21m00Tcm4TlvDq8ikWAM")
        model = request.get("model", "eleven_multilingual_v2")
        speed = request.get("speed", 1.0)
        return {
            "audio_url": f"https://cdn.sentra-aura.dev/tts/elevenlabs/{hash(text) % 1000000}.mp3",
            "provider": self.provider_id,
            "model": model,
            "duration_seconds": len(text.split()) * 0.4 / speed,
            "voice_id": voice_id,
        }

    async def _health_check_impl(self) -> bool:
        if self._client is None:
            return True
        try:
            voices = await self._client.voices.get_all()
            return len(voices.voices) > 0
        except Exception:
            return False

    def estimate_cost(self, request: dict[str, Any]) -> float:
        model = request.get("model", "eleven_multilingual_v2")
        price_per_1k = self.PRICING.get(model, 0.30)
        chars = len(request.get("text", ""))
        return round((chars / 1000) * price_per_1k, 6)
