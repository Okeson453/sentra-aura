from __future__ import annotations
import os
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class VisualAssetConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VISUAL_ASSET_", extra="ignore")
    agent_name: str = "visual_asset_agent"
    timeout_seconds: float = 60.0
    provider_gateway_url: str = Field(default_factory=lambda: os.environ.get("PROVIDER_GATEWAY_URL", "http://localhost:8081"))
    default_model: str = "mock-gpt-4"
    default_image_size: str = "1024x1024"
