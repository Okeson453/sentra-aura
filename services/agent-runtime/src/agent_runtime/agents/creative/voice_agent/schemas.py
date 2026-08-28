"""Schemas for Voice Agent (Architecture §4.2).

Inputs: polished script, voice profile.
Outputs: audio segments with word-level timing, TTS metadata.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class VoiceSegment(BaseModel):
    id: str
    text: str
    duration_estimate: float = 0.0
    duration_seconds: float = 0.0
    emotion: str = "neutral"
    emphasis_words: list[str] = Field(default_factory=list)
    phonetic_notes: dict[str, str] = Field(default_factory=dict)
    pause_instructions: list[str] = Field(default_factory=list)
    audio_url: str | None = None
    word_timings: list[dict[str, Any]] = Field(default_factory=list)
    tts_provider: str | None = None


class VoiceRequest(BaseModel):
    # Scripting agent ScriptResponse.script or full ScriptResponse dump
    script: dict[str, Any] = Field(default_factory=dict)
    # Optional: full scripting_agent output envelope
    script_response: dict[str, Any] | None = None
    voice_profile: str = "neutral"
    language: str = "en"
    pacing: str = "conversational"
    target_platform: str = "youtube"
    task_type: str = "synthesize"


class VoiceResponse(BaseModel):
    segments: list[VoiceSegment] = Field(default_factory=list)
    voice_profile_recommendation: dict[str, Any] = Field(default_factory=dict)
    pacing_notes: str = ""
    consistency_checklist: list[str] = Field(default_factory=list)
    tts_metadata: dict[str, Any] = Field(default_factory=dict)
    total_duration_seconds: float = 0.0
    raw_provider_text: str | None = None
    provider_usage: dict[str, Any] | None = None
