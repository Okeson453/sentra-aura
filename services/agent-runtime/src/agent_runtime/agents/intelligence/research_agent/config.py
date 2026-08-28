"""Configuration for Research Agent."""
from __future__ import annotations

import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ResearchAgentConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RESEARCH_AGENT_", extra="ignore")

    agent_name: str = "research_agent"
    timeout_seconds: float = 90.0
    research_service_url: str = Field(
        default_factory=lambda: os.environ.get(
            "RESEARCH_SERVICE_URL", "http://localhost:8020"
        )
    )
    research_service_token: str = Field(
        default_factory=lambda: os.environ.get("RESEARCH_SERVICE_TOKEN", "dev-token")
    )
    provider_gateway_url: str = Field(
        default_factory=lambda: os.environ.get(
            "PROVIDER_GATEWAY_URL", "http://localhost:8081"
        )
    )
    default_model: str = "mock-gpt-4"
    temperature: float = 0.2
    max_tokens: int = 2500
    poll_interval_seconds: float = 0.15
    poll_max_attempts: int = 40
