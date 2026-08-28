from __future__ import annotations

import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AI_CLIPPING_AGENT_", extra="ignore")
    agent_name: str = "ai_clipping_agent"
    timeout_seconds: float = 60.0
    provider_gateway_url: str = Field(
        default_factory=lambda: os.environ.get("PROVIDER_GATEWAY_URL", "http://localhost:8081")
    )
    default_model: str = "mock-gpt-4"
    max_clips: int = 5
    score_threshold: float = 0.35
    clipping_engine_url: str = Field(
        default_factory=lambda: os.environ.get("CLIPPING_ENGINE_URL", "http://localhost:8000")
    )
