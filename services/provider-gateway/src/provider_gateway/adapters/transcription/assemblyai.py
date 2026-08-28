"""AssemblyAI adapter for transcription, speaker diarization, and PII redaction."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from provider_gateway.adapters.base import BaseProviderAdapter, ProviderCapability
from provider_gateway.config import ProviderConfig

logger = logging.getLogger(__name__)


class AssemblyAIAdapter(BaseProviderAdapter[dict[str, Any]]):
    """AssemblyAI adapter with speaker labels, sentiment, and PII redaction."""

    MODELS = [
        {"model_id": "best", "name": "Best (Default)", "capabilities": ["transcribe"]},
        {"model_id": "nano", "name": "Nano (Fast)", "capabilities": ["transcribe"]},
    ]

    # Pricing per hour of audio
    PRICING = {
        "best": 0.37,
        "nano": 0.12,
    }

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._client: Any = None
        self._base_url = config.base_url or "https://api.assemblyai.com/v2"
        try:
            import httpx
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={"Authorization": config.api_key},
                timeout=config.timeout_seconds,
            )
        except ImportError:
            logger.warning("httpx not installed; AssemblyAI adapter in mock mode")

    @property
    def provider_id(self) -> str:
        return "assemblyai"

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
        model = request.get("model", "best")
        speaker_labels = request.get("speaker_labels", False)
        sentiment_analysis = request.get("sentiment_analysis", False)
        pii_redaction = request.get("pii_redaction", False)
        language_code = request.get("language_code", "en_us")

        # Submit transcription job
        payload = {
            "audio_url": audio_url if not audio_file_path else None,
            "speech_model": model,
            "speaker_labels": speaker_labels,
            "sentiment_analysis": sentiment_analysis,
            "redact_pii": pii_redaction,
            "language_code": language_code,
        }
        payload = {k: v for k, v in payload.items() if v is not None}

        resp = await self._client.post("/transcript", json=payload)
        resp.raise_for_status()
        transcript = resp.json()
        transcript_id = transcript["id"]

        # Poll for completion
        max_wait = 300  # 5 minutes
        poll_interval = 5
        for _ in range(max_wait // poll_interval):
            status_resp = await self._client.get(f"/transcript/{transcript_id}")
            status_resp.raise_for_status()
            status = status_resp.json()
            if status["status"] == "completed":
                return self._format_result(status, model)
            if status["status"] == "error":
                raise RuntimeError(f"AssemblyAI transcription failed: {status.get('error')}")
            await asyncio.sleep(poll_interval)

        raise TimeoutError("AssemblyAI transcription timed out")

    def _format_result(self, status: dict[str, Any], model: str) -> dict[str, Any]:
        utterances = []
        for u in status.get("utterances", []):
            utterances.append({
                "speaker": u.get("speaker"),
                "text": u.get("text"),
                "start": u.get("start"),
                "end": u.get("end"),
                "confidence": u.get("confidence"),
            })

        return {
            "text": status.get("text", ""),
            "provider": self.provider_id,
            "model": model,
            "language": status.get("language_code", "en_us"),
            "duration_seconds": status.get("audio_duration", 0),
            "utterances": utterances,
            "confidence": status.get("confidence"),
            "sentiment_analysis_results": status.get("sentiment_analysis_results", []),
            "words": status.get("words", []),
        }

    def _mock_execute(self, request: dict[str, Any]) -> dict[str, Any]:
        audio_url = request.get("audio_url", "")
        model = request.get("model", "best")
        duration = request.get("duration_seconds", 60)
        return {
            "text": "[MOCK AssemblyAI transcription with speaker diarization enabled.]",
            "provider": self.provider_id,
            "model": model,
            "language": request.get("language_code", "en_us"),
            "duration_seconds": duration,
            "utterances": [
                {"speaker": "A", "text": "Hello and welcome.", "start": 0, "end": 2000, "confidence": 0.98},
                {"speaker": "B", "text": "Thank you for having me.", "start": 2500, "end": 4500, "confidence": 0.95},
            ],
            "confidence": 0.97,
            "sentiment_analysis_results": [],
            "words": [],
        }

    async def _health_check_impl(self) -> bool:
        if self._client is None:
            return True
        try:
            resp = await self._client.get("/transcript/recent")
            return resp.status_code == 200
        except Exception:
            return False

    def estimate_cost(self, request: dict[str, Any]) -> float:
        model = request.get("model", "best")
        duration = request.get("duration_seconds", 60)
        hours = duration / 3600.0
        rate = self.PRICING.get(model, 0.37)
        return round(hours * rate, 6)
