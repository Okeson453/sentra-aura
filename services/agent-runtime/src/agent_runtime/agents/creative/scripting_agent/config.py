"""Configuration for the Scripting Agent."""
from __future__ import annotations

import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ScriptingAgentConfig(BaseSettings):
    """Settings loaded from environment (prefix SCRIPTING_)."""

    model_config = SettingsConfigDict(env_prefix="SCRIPTING_", extra="ignore")

    agent_name: str = "scripting_agent"
    max_retries: int = 3
    timeout_seconds: float = 120.0
    provider_gateway_url: str = Field(
        default_factory=lambda: os.environ.get(
            "PROVIDER_GATEWAY_URL", "http://localhost:8081"
        )
    )
    default_model: str = "mock-gpt-4"
    temperature: float = 0.7
    max_tokens: int = 2000
    max_reflection_rounds: int = 1
    enable_sponsorship_injection: bool = True
