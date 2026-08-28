"""Configuration for Voice Agent."""
from __future__ import annotations

import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class VoiceAgentConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VOICE_AGENT_", extra="ignore")

    agent_name: str = "voice_agent"
    timeout_seconds: float = 60.0
    provider_gateway_url: str = Field(
        default_factory=lambda: os.environ.get(
            "PROVIDER_GATEWAY_URL", "http://localhost:8081"
        )
    )
    default_model: str = "mock-gpt-4"
    default_voice: str = "mock-voice-1"
    temperature: float = 0.3
    max_tokens: int = 2000
