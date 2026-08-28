"""Provider Gateway configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProviderConfig:
    """Configuration for a single provider."""

    provider_id: str
    api_key: str | None = None
    base_url: str | None = None
    timeout_seconds: float = 60.0
    max_retries: int = 3
    retry_backoff_base: float = 1.0
    enabled: bool = True
    priority: int = 0
    rate_limit_rpm: int = 60
    extra_headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class GatewayConfig:
    """Top-level gateway configuration."""

    service_name: str = "provider-gateway"
    version: str = "1.0.0"
    port: int = 8000
    log_level: str = "INFO"
    otel_endpoint: str | None = None
    jaeger_endpoint: str | None = None
    default_fallback_allowed: bool = True
    cost_budget_usd_per_channel_per_day: float = 100.0
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout_seconds: float = 30.0
    providers: dict[str, ProviderConfig] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> GatewayConfig:
        """Build configuration from environment variables."""
        providers: dict[str, ProviderConfig] = {}

        # LLM providers
        for provider_id, env_key, base_url in [
            ("openai", "OPENAI_API_KEY", "https://api.openai.com/v1"),
            ("anthropic", "ANTHROPIC_API_KEY", "https://api.anthropic.com/v1"),
            ("google", "GOOGLE_API_KEY", "https://generativelanguage.googleapis.com/v1"),
            ("cohere", "COHERE_API_KEY", "https://api.cohere.com/v1"),
            ("mistral", "MISTRAL_API_KEY", "https://api.mistral.ai/v1"),
        ]:
            api_key = os.environ.get(env_key)
            if api_key:
                providers[provider_id] = ProviderConfig(
                    provider_id=provider_id,
                    api_key=api_key,
                    base_url=os.environ.get(f"{env_key}_BASE_URL", base_url),
                    timeout_seconds=float(os.environ.get(f"{env_key}_TIMEOUT", "60")),
                    max_retries=int(os.environ.get(f"{env_key}_MAX_RETRIES", "3")),
                    rate_limit_rpm=int(os.environ.get(f"{env_key}_RPM", "60")),
                )

        # TTS providers
        for provider_id, env_key, base_url in [
            ("elevenlabs", "ELEVENLABS_API_KEY", "https://api.elevenlabs.io/v1"),
            ("azure_tts", "AZURE_TTS_KEY", None),
            ("aws_tts", "AWS_TTS_KEY", None),
        ]:
            api_key = os.environ.get(env_key)
            if api_key:
                providers[provider_id] = ProviderConfig(
                    provider_id=provider_id,
                    api_key=api_key,
                    base_url=os.environ.get(f"{env_key}_BASE_URL", base_url),
                )

        # Image providers
        for provider_id, env_key, base_url in [
            ("dalle", "DALLE_API_KEY", "https://api.openai.com/v1"),
            ("midjourney", "MIDJOURNEY_API_KEY", "https://api.midjourney.com/v1"),
            ("stablediffusion", "STABLE_DIFFUSION_KEY", "https://api.stability.ai/v2"),
        ]:
            api_key = os.environ.get(env_key)
            if api_key:
                providers[provider_id] = ProviderConfig(
                    provider_id=provider_id,
                    api_key=api_key,
                    base_url=os.environ.get(f"{env_key}_BASE_URL", base_url),
                )

        # Video providers
        for provider_id, env_key, base_url in [
            ("runway", "RUNWAY_API_KEY", "https://api.runwayml.com/v1"),
            ("pika", "PIKA_API_KEY", "https://api.pika.art/v1"),
        ]:
            api_key = os.environ.get(env_key)
            if api_key:
                providers[provider_id] = ProviderConfig(
                    provider_id=provider_id,
                    api_key=api_key,
                    base_url=os.environ.get(f"{env_key}_BASE_URL", base_url),
                )

        # Search providers
        for provider_id, env_key, base_url in [
            ("serpapi", "SERPAPI_KEY", "https://serpapi.com/search"),
            ("tavily", "TAVILY_API_KEY", "https://api.tavily.com"),
        ]:
            api_key = os.environ.get(env_key)
            if api_key:
                providers[provider_id] = ProviderConfig(
                    provider_id=provider_id,
                    api_key=api_key,
                    base_url=os.environ.get(f"{env_key}_BASE_URL", base_url),
                )

        # Transcription providers
        for provider_id, env_key, base_url in [
            ("whisper", "WHISPER_API_KEY", "https://api.openai.com/v1"),
            ("assemblyai", "ASSEMBLYAI_KEY", "https://api.assemblyai.com/v2"),
        ]:
            api_key = os.environ.get(env_key)
            if api_key:
                providers[provider_id] = ProviderConfig(
                    provider_id=provider_id,
                    api_key=api_key,
                    base_url=os.environ.get(f"{env_key}_BASE_URL", base_url),
                )

        return cls(
            service_name=os.environ.get("SERVICE_NAME", "provider-gateway"),
            version=os.environ.get("SERVICE_VERSION", "1.0.0"),
            port=int(os.environ.get("PORT", "8000")),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
            otel_endpoint=os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"),
            jaeger_endpoint=os.environ.get("JAEGER_ENDPOINT"),
            default_fallback_allowed=os.environ.get("FALLBACK_ALLOWED", "true").lower() == "true",
            cost_budget_usd_per_channel_per_day=float(
                os.environ.get("COST_BUDGET_PER_CHANNEL_PER_DAY", "100.0")
            ),
            circuit_breaker_failure_threshold=int(
                os.environ.get("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5")
            ),
            circuit_breaker_recovery_timeout_seconds=float(
                os.environ.get("CIRCUIT_BREAKER_RECOVERY_TIMEOUT", "30.0")
            ),
            providers=providers,
        )
