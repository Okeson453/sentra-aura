"""Research Service configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ResearchConfig:
    """Top-level research service configuration."""

    service_name: str = "research-service"
    version: str = "1.0.0"
    port: int = 8000
    log_level: str = "INFO"
    otel_endpoint: str | None = None
    jaeger_endpoint: str | None = None
    provider_gateway_url: str = "http://provider-gateway:8000"
    provider_gateway_api_key: str | None = None
    max_sources_per_query: int = 20
    default_research_depth: str = "standard"
    credibility_threshold: float = 0.6
    pii_filter_enabled: bool = True
    pii_filter_strictness: str = "high"  # low, medium, high
    claim_extraction_min_confidence: float = 0.7
    cache_ttl_seconds: int = 3600
    rate_limit_rpm: int = 60
    request_timeout_seconds: float = 30.0
    database_url: str | None = None
    redis_url: str | None = None
    vector_store_url: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> ResearchConfig:
        """Build configuration from environment variables."""
        return cls(
            service_name=os.environ.get("SERVICE_NAME", "research-service"),
            version=os.environ.get("SERVICE_VERSION", "1.0.0"),
            port=int(os.environ.get("PORT", "8000")),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
            otel_endpoint=os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"),
            jaeger_endpoint=os.environ.get("JAEGER_ENDPOINT"),
            provider_gateway_url=os.environ.get("PROVIDER_GATEWAY_URL", "http://provider-gateway:8000"),
            provider_gateway_api_key=os.environ.get("PROVIDER_GATEWAY_API_KEY"),
            max_sources_per_query=int(os.environ.get("MAX_SOURCES_PER_QUERY", "20")),
            default_research_depth=os.environ.get("DEFAULT_RESEARCH_DEPTH", "standard"),
            credibility_threshold=float(os.environ.get("CREDIBILITY_THRESHOLD", "0.6")),
            pii_filter_enabled=os.environ.get("PII_FILTER_ENABLED", "true").lower() == "true",
            pii_filter_strictness=os.environ.get("PII_FILTER_STRICTNESS", "high"),
            claim_extraction_min_confidence=float(os.environ.get("CLAIM_MIN_CONFIDENCE", "0.7")),
            cache_ttl_seconds=int(os.environ.get("CACHE_TTL_SECONDS", "3600")),
            rate_limit_rpm=int(os.environ.get("RATE_LIMIT_RPM", "60")),
            request_timeout_seconds=float(os.environ.get("REQUEST_TIMEOUT_SECONDS", "30.0")),
            database_url=os.environ.get("DATABASE_URL"),
            redis_url=os.environ.get("REDIS_URL"),
            vector_store_url=os.environ.get("VECTOR_STORE_URL"),
        )
