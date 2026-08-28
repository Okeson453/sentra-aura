from __future__ import annotations
import os
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class AgentConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VIDEO_PRODUCTION_AGENT_", extra="ignore")
    agent_name: str = "video_production_agent"
    timeout_seconds: float = 60.0
    provider_gateway_url: str = Field(default_factory=lambda: os.environ.get("PROVIDER_GATEWAY_URL", "http://localhost:8081"))
    default_model: str = "mock-gpt-4"
    media_renderer_url: str = Field(
        default_factory=lambda: os.environ.get("MEDIA_RENDERER_URL", "http://localhost:8000")
    )
