"""Configuration for Content Strategist & Ideation Agent."""
from __future__ import annotations

import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ContentStrategistConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CONTENT_STRATEGIST_", extra="ignore")

    agent_name: str = "content_strategist_ideation_agent"
    timeout_seconds: float = 60.0
    provider_gateway_url: str = Field(
        default_factory=lambda: os.environ.get(
            "PROVIDER_GATEWAY_URL", "http://localhost:8081"
        )
    )
    default_model: str = "mock-gpt-4"
    temperature: float = 0.5
    max_tokens: int = 2500
    default_num_concepts: int = 5
