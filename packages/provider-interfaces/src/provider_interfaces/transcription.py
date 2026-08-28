"""Transcription provider interface for SentraAura."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SpeakerSegment:
    """A single speaker segment from diarization."""
    speaker_id: str
    start_ms: int
    end_ms: int
    text: str = ""


@dataclass
class TranscriptResponse:
    """Response from a transcription provider."""
    text: str = ""
    segments: list[dict[str, Any]] = field(default_factory=list)
    word_timings: list[dict[str, Any]] = field(default_factory=list)
    speaker_segments: list[SpeakerSegment] = field(default_factory=list)
    language: str = "en"
    confidence: float = 0.0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    provider: str = ""
    trace_id: str = ""


class TranscriptionProvider(ABC):
    """Abstract interface for transcription providers."""

    @abstractmethod
    async def transcribe(self, audio: bytes, options: dict[str, Any] | None = None) -> TranscriptResponse:
        """Transcribe audio to text with word-level timestamps."""
        ...

    @abstractmethod
    async def diarize(self, audio: bytes, num_speakers: int | None = None) -> list[SpeakerSegment]:
        """Perform speaker diarization on audio."""
        ...

    @abstractmethod
    async def health_check(self) -> tuple[bool, str]:
        """Return (healthy, message) for this provider."""
        ...
