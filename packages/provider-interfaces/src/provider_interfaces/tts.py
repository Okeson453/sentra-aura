"""TTS provider interface for SentraAura."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class VoiceProfile:
    """Voice configuration for TTS synthesis."""
    voice_id: str
    name: str = ""
    language: str = "en"
    gender: str = "neutral"
    style: str = "neutral"
    speed: float = 1.0
    pitch: float = 1.0


@dataclass
class TTSResponse:
    """Response from a TTS provider."""
    audio_bytes: bytes
    duration_seconds: float = 0.0
    format: str = "mp3"
    sample_rate: int = 24000
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    provider: str = ""
    trace_id: str = ""
    word_timings: list[dict[str, Any]] | None = None


class TTSProvider(ABC):
    """Abstract interface for TTS providers."""

    @abstractmethod
    async def synthesize(self, text: str, voice: VoiceProfile, output_format: str = "mp3") -> TTSResponse:
        """Synthesize speech from text."""
        ...

    @abstractmethod
    async def list_voices(self) -> list[VoiceProfile]:
        """List available voices."""
        ...

    @abstractmethod
    async def clone_voice(self, audio_samples: list[bytes], name: str) -> str:
        """Clone a voice from audio samples; returns voice_id."""
        ...

    @abstractmethod
    async def health_check(self) -> tuple[bool, str]:
        """Return (healthy, message) for this provider."""
        ...
