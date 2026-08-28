"""Azure Cognitive Services Speech TTS adapter with SSML support."""

from __future__ import annotations

import logging
from typing import Any

from provider_gateway.adapters.base import BaseProviderAdapter, ProviderCapability
from provider_gateway.config import ProviderConfig

logger = logging.getLogger(__name__)


class AzureTTSAdapter(BaseProviderAdapter[dict[str, Any]]):
    """Azure Speech Services TTS with SSML and neural voices."""

    MODELS = [
        {"model_id": "en-US-AriaNeural", "name": "Aria (US English)", "capabilities": ["tts"]},
        {"model_id": "en-US-GuyNeural", "name": "Guy (US English)", "capabilities": ["tts"]},
        {"model_id": "en-GB-SoniaNeural", "name": "Sonia (UK English)", "capabilities": ["tts"]},
        {"model_id": "en-AU-NatashaNeural", "name": "Natasha (AU English)", "capabilities": ["tts"]},
    ]

    # Pricing per 1M characters (neural)
    PRICING_PER_1M_CHARS = 16.0

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._client: Any = None
        self._region = config.extra_headers.get("region", "westus2")
        try:
            import azure.cognitiveservices.speech as speechsdk
            self._speech_config = speechsdk.SpeechConfig(
                subscription=config.api_key,
                region=self._region,
            )
            self._client = speechsdk
        except ImportError:
            logger.warning("azure-cognitiveservices-speech not installed; Azure TTS in mock mode")

    @property
    def provider_id(self) -> str:
        return "azure_tts"

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
        voice = request.get("voice", "en-US-AriaNeural")
        speed = request.get("speed", 1.0)

        self._speech_config.speech_synthesis_voice_name = voice
        synthesizer = self._client.SpeechSynthesizer(speech_config=self._speech_config)

        if speed != 1.0:
            ssml = f'''<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">
                <voice name="{voice}"><prosody rate="{int((speed - 1.0) * 100)}%">{text}</prosody></voice>
            </speak>'''
            result = synthesizer.speak_ssml_async(ssml).get()
        else:
            result = synthesizer.speak_text_async(text).get()

        if result.reason == self._client.ResultReason.SynthesizingAudioCompleted:
            return {
                "audio_url": f"https://cdn.sentra-aura.dev/tts/azure/{hash(text) % 1000000}.wav",
                "provider": self.provider_id,
                "model": voice,
                "duration_seconds": len(text.split()) * 0.45 / speed,
                "voice_id": voice,
            }
        raise RuntimeError(f"Azure TTS failed: {result.reason}")

    def _mock_execute(self, request: dict[str, Any]) -> dict[str, Any]:
        text = request.get("text", "")
        voice = request.get("voice", "en-US-AriaNeural")
        speed = request.get("speed", 1.0)
        return {
            "audio_url": f"https://cdn.sentra-aura.dev/tts/azure/{hash(text) % 1000000}.wav",
            "provider": self.provider_id,
            "model": voice,
            "duration_seconds": len(text.split()) * 0.45 / speed,
            "voice_id": voice,
        }

    async def _health_check_impl(self) -> bool:
        if self._client is None:
            return True
        try:
            synthesizer = self._client.SpeechSynthesizer(speech_config=self._speech_config)
            result = synthesizer.speak_text_async("test").get()
            return result.reason == self._client.ResultReason.SynthesizingAudioCompleted
        except Exception:
            return False

    def estimate_cost(self, request: dict[str, Any]) -> float:
        chars = len(request.get("text", ""))
        return round((chars / 1_000_000) * self.PRICING_PER_1M_CHARS, 6)
