"""OpenAI Whisper adapter for speech-to-text with timestamp and language detection."""

from __future__ import annotations

import logging
from typing import Any

from provider_gateway.adapters.base import BaseProviderAdapter, ProviderCapability
from provider_gateway.config import ProviderConfig

logger = logging.getLogger(__name__)


class WhisperAdapter(BaseProviderAdapter[dict[str, Any]]):
    """OpenAI Whisper adapter for audio transcription and translation."""

    MODELS = [
        {"model_id": "whisper-1", "name": "Whisper v1", "capabilities": ["transcribe"]},
    ]

    # Pricing per minute of audio
    PRICING_PER_MINUTE = 0.006

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
            logger.warning("openai package not installed; Whisper adapter in mock mode")

    @property
    def provider_id(self) -> str:
        return "whisper"

    @property
    def capabilities(self) -> list[ProviderCapability]:
        return [ProviderCapability.TRANSCRIBE]

    @property
    def models(self) -> list[dict[str, Any]]:
        return self.MODELS

    async def _execute(self, request: dict[str, Any]) -> dict[str, Any]:
        if self._client is None:
            return self._mock_execute(request)

        audio_url = request.get("audio_url", "")
        audio_file_path = request.get("audio_file_path")
        language = request.get("language")
        response_format = request.get("response_format", "json")
        timestamp_granularities = request.get("timestamp_granularities", ["segment"])

        if audio_file_path:
            with open(audio_file_path, "rb") as audio_file:
                resp = await self._client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=language,
                    response_format=response_format,
                    timestamp_granularities=timestamp_granularities,
                )
        else:
            # For URL-based audio, download first
            import httpx
            async with httpx.AsyncClient() as client:
                audio_resp = await client.get(audio_url)
                audio_resp.raise_for_status()
                from io import BytesIO
                audio_file = BytesIO(audio_resp.content)
                resp = await self._client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=language,
                    response_format=response_format,
                    timestamp_granularities=timestamp_granularities,
                )

        text = resp.text if hasattr(resp, "text") else str(resp)
        duration = request.get("duration_seconds", 60)
        return {
            "text": text,
            "provider": self.provider_id,
            "model": "whisper-1",
            "language": language or "auto",
            "duration_seconds": duration,
            "audio_url": audio_url,
        }

    def _mock_execute(self, request: dict[str, Any]) -> dict[str, Any]:
        audio_url = request.get("audio_url", "")
        duration = request.get("duration_seconds", 60)
        return {
            "text": "[MOCK Whisper transcription: This is a sample transcribed text from the audio file.]",
            "provider": self.provider_id,
            "model": "whisper-1",
            "language": request.get("language", "auto"),
            "duration_seconds": duration,
            "audio_url": audio_url,
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
        duration = request.get("duration_seconds", 60)
        minutes = duration / 60.0
        return round(minutes * self.PRICING_PER_MINUTE, 6)
