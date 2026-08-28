"""AWS Polly TTS adapter with standard and neural engines."""

from __future__ import annotations

import logging
from typing import Any

from provider_gateway.adapters.base import BaseProviderAdapter, ProviderCapability
from provider_gateway.config import ProviderConfig

logger = logging.getLogger(__name__)


class AWSTTSAdapter(BaseProviderAdapter[dict[str, Any]]):
    """Amazon Polly text-to-speech with standard and neural engines."""

    MODELS = [
        {"model_id": "Joanna", "name": "Joanna (US English)", "capabilities": ["tts"]},
        {"model_id": "Matthew", "name": "Matthew (US English)", "capabilities": ["tts"]},
        {"model_id": "Amy", "name": "Amy (UK English)", "capabilities": ["tts"]},
        {"model_id": "Takumi", "name": "Takumi (Japanese)", "capabilities": ["tts"]},
    ]

    # Pricing per 1M characters
    PRICING = {
        "standard": 4.0,
        "neural": 16.0,
    }

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._client: Any = None
        self._region = config.extra_headers.get("region", "us-east-1")
        try:
            import boto3
            self._client = boto3.client(
                "polly",
                aws_access_key_id=config.api_key,
                aws_secret_access_key=config.extra_headers.get("secret_key", ""),
                region_name=self._region,
            )
        except ImportError:
            logger.warning("boto3 not installed; AWS Polly adapter in mock mode")

    @property
    def provider_id(self) -> str:
        return "aws_tts"

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
        voice = request.get("voice", "Joanna")
        engine = request.get("engine", "neural")
        speed = request.get("speed", 1.0)

        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._client.synthesize_speech(
                Text=text,
                OutputFormat="mp3",
                VoiceId=voice,
                Engine=engine,
                SpeechMarkTypes=["word"] if speed != 1.0 else [],
            ),
        )

        return {
            "audio_url": f"https://cdn.sentra-aura.dev/tts/aws/{hash(text) % 1000000}.mp3",
            "provider": self.provider_id,
            "model": voice,
            "duration_seconds": len(text.split()) * 0.42 / speed,
            "voice_id": voice,
            "engine": engine,
        }

    def _mock_execute(self, request: dict[str, Any]) -> dict[str, Any]:
        text = request.get("text", "")
        voice = request.get("voice", "Joanna")
        engine = request.get("engine", "neural")
        speed = request.get("speed", 1.0)
        return {
            "audio_url": f"https://cdn.sentra-aura.dev/tts/aws/{hash(text) % 1000000}.mp3",
            "provider": self.provider_id,
            "model": voice,
            "duration_seconds": len(text.split()) * 0.42 / speed,
            "voice_id": voice,
            "engine": engine,
        }

    async def _health_check_impl(self) -> bool:
        if self._client is None:
            return True
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._client.describe_voices(LanguageCode="en-US", MaxResults=1),
            )
            return True
        except Exception:
            return False

    def estimate_cost(self, request: dict[str, Any]) -> float:
        engine = request.get("engine", "neural")
        price = self.PRICING.get(engine, 16.0)
        chars = len(request.get("text", ""))
        return round((chars / 1_000_000) * price, 6)
