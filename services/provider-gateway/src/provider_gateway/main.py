"""Provider Gateway FastAPI service entrypoint."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from provider_gateway.config import GatewayConfig
from provider_gateway.router import ProviderRouter, NoProviderAvailableError, AllProvidersFailedError
from provider_gateway.cost_tracker import CostTracker
from provider_gateway.llm_tracer import LLMTracer
from provider_gateway.adapters.base import ProviderCapability

# Provider adapters — imported lazily to avoid loading unused providers
from provider_gateway.adapters.llm.openai import OpenAIAdapter
from provider_gateway.adapters.llm.anthropic import AnthropicAdapter
from provider_gateway.adapters.llm.google import GoogleAdapter
from provider_gateway.adapters.llm.cohere import CohereAdapter
from provider_gateway.adapters.llm.mistral import MistralAdapter
from provider_gateway.adapters.tts.elevenlabs import ElevenLabsAdapter
from provider_gateway.adapters.tts.azure import AzureTTSAdapter
from provider_gateway.adapters.tts.aws import AWSTTSAdapter
from provider_gateway.adapters.image.dalle import DALLEAdapter
from provider_gateway.adapters.image.midjourney import MidjourneyAdapter
from provider_gateway.adapters.image.stablediffusion import StableDiffusionAdapter
from provider_gateway.adapters.video.runway import RunwayAdapter
from provider_gateway.adapters.video.pika import PikaAdapter
from provider_gateway.adapters.search.serpapi import SerpAPIAdapter
from provider_gateway.adapters.search.tavily import TavilyAdapter
from provider_gateway.adapters.transcription.whisper import WhisperAdapter
from provider_gateway.adapters.transcription.assemblyai import AssemblyAIAdapter

logger = logging.getLogger(__name__)

config: GatewayConfig
router: ProviderRouter
cost_tracker: CostTracker
llm_tracer: LLMTracer


@asynccontextmanager
async def lifespan(app: FastAPI):
    global config, router, cost_tracker, llm_tracer
    config = GatewayConfig.from_env()
    logging.basicConfig(level=getattr(logging, config.log_level.upper(), logging.INFO))

    cost_tracker = CostTracker()
    llm_tracer = LLMTracer(
        service_name=config.service_name,
        otel_endpoint=config.otel_endpoint,
    )
    router = ProviderRouter(config=config, cost_tracker=cost_tracker)

    # Register all configured adapters
    adapter_map = {
        "openai": OpenAIAdapter,
        "anthropic": AnthropicAdapter,
        "google": GoogleAdapter,
        "cohere": CohereAdapter,
        "mistral": MistralAdapter,
        "elevenlabs": ElevenLabsAdapter,
        "azure_tts": AzureTTSAdapter,
        "aws_tts": AWSTTSAdapter,
        "dalle": DALLEAdapter,
        "midjourney": MidjourneyAdapter,
        "stablediffusion": StableDiffusionAdapter,
        "runway": RunwayAdapter,
        "pika": PikaAdapter,
        "serpapi": SerpAPIAdapter,
        "tavily": TavilyAdapter,
        "whisper": WhisperAdapter,
        "assemblyai": AssemblyAIAdapter,
    }

    for provider_id, adapter_cls in adapter_map.items():
        provider_cfg = config.providers.get(provider_id)
        if provider_cfg and provider_cfg.enabled:
            try:
                adapter = adapter_cls(provider_cfg)
                router.register(adapter)
            except Exception as exc:
                logger.error("Failed to register adapter %s: %s", provider_id, exc)

    logger.info("Provider Gateway started with %d providers", len(router._adapters))
    yield
    logger.info("Provider Gateway shutting down")


app = FastAPI(
    title="SentraAura Provider Gateway",
    version="1.0.0",
    lifespan=lifespan,
)


def _require_api_key(x_api_key: str | None = Header(None, alias="X-API-Key")) -> str:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    # In production, validate against a secrets manager or vault
    return x_api_key


@app.get("/health")
async def health_check() -> dict[str, Any]:
    return {
        "status": "healthy",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "version": config.version,
    }


@app.get("/ready")
async def readiness_check() -> dict[str, Any]:
    health_map = await router.health_check_all()
    any_healthy = any(v in ("healthy", "degraded") for v in health_map.values())
    status = "healthy" if any_healthy else "unhealthy"
    return {
        "status": status,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "version": config.version,
        "checks": {pid: {"status": h, "latency_ms": 0.0} for pid, h in health_map.items()},
    }


@app.post("/v1/complete")
async def llm_complete(request: Request, api_key: str = _require_api_key) -> dict[str, Any]:
    body = await request.json()
    prompt = body.get("prompt", "")
    task_type = body.get("task_type", "unknown")
    model = body.get("model")
    temperature = body.get("temperature", 0.7)
    max_tokens = body.get("max_tokens", 1024)
    channel_id = body.get("channel_id")
    fallback_allowed = body.get("fallback_allowed", True)
    preferred = body.get("preferred_provider")

    llm_request = {
        "prompt": prompt,
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    span = llm_tracer.start_span(
        operation="complete",
        provider_id=preferred or "auto",
        model=model,
        channel_id=channel_id,
        task_type=task_type,
        prompt_tokens=len(prompt.split()),  # rough estimate
        max_tokens=max_tokens,
        temperature=temperature,
    )

    try:
        with span:
            result = await router.route(
                capability=ProviderCapability.LLM_COMPLETE,
                request=llm_request,
                preferred_provider=preferred,
                fallback_allowed=fallback_allowed,
                channel_id=channel_id,
                task_type=task_type,
            )

            llm_tracer.record_completion(
                span_context=span,
                completion_tokens=result.data.get("completion_tokens", 0),
                latency_ms=result.latency_ms,
                estimated_cost_usd=result.estimated_cost_usd,
                fallback_used=result.fallback_used,
            )

            return {
                "text": result.data.get("text", ""),
                "provider": result.provider_id,
                "model": result.model or model,
                "usage": {
                    "prompt_tokens": result.data.get("prompt_tokens", 0),
                    "completion_tokens": result.data.get("completion_tokens", 0),
                    "total_tokens": result.data.get("total_tokens", 0),
                    "estimated_cost_usd": result.estimated_cost_usd,
                },
                "latency_ms": result.latency_ms,
                "fallback_used": result.fallback_used,
            }
    except NoProviderAvailableError:
        raise HTTPException(status_code=503, detail="No provider available for LLM completion")
    except AllProvidersFailedError as exc:
        llm_tracer.record_completion(
            span_context=span,
            completion_tokens=0,
            latency_ms=exc.latency_ms,
            estimated_cost_usd=0.0,
            fallback_used=True,
            error=exc,
        )
        raise HTTPException(status_code=503, detail=f"All providers failed: {exc.last_error}")


@app.post("/v1/embed")
async def embed_text(request: Request, api_key: str = _require_api_key) -> dict[str, Any]:
    body = await request.json()
    text = body.get("text", "")
    model = body.get("model")
    dimensions = body.get("dimensions")
    channel_id = body.get("channel_id")

    embed_request = {"text": text, "model": model, "dimensions": dimensions}
    result = await router.route(
        capability=ProviderCapability.EMBED,
        request=embed_request,
        channel_id=channel_id,
        task_type="embed",
    )
    return {
        "embedding": result.data.get("embedding", []),
        "provider": result.provider_id,
        "model": result.model or model,
        "usage": {
            "prompt_tokens": result.data.get("prompt_tokens", 0),
            "estimated_cost_usd": result.estimated_cost_usd,
        },
    }


@app.post("/v1/tts")
async def text_to_speech(request: Request, api_key: str = _require_api_key) -> dict[str, Any]:
    body = await request.json()
    tts_request = {
        "text": body.get("text", ""),
        "voice": body.get("voice"),
        "speed": body.get("speed", 1.0),
    }
    result = await router.route(
        capability=ProviderCapability.TTS,
        request=tts_request,
        channel_id=body.get("channel_id"),
        task_type="tts",
    )
    return {
        "audio_url": result.data.get("audio_url", ""),
        "provider": result.provider_id,
        "duration_seconds": result.data.get("duration_seconds", 0.0),
    }


@app.post("/v1/images/generate")
async def generate_image(request: Request, api_key: str = _require_api_key) -> dict[str, Any]:
    body = await request.json()
    img_request = {
        "prompt": body.get("prompt", ""),
        "size": body.get("size", "1024x1024"),
        "style": body.get("style"),
    }
    result = await router.route(
        capability=ProviderCapability.IMAGE_GENERATE,
        request=img_request,
        channel_id=body.get("channel_id"),
        task_type="image_generate",
    )
    return {
        "image_url": result.data.get("image_url", ""),
        "provider": result.provider_id,
        "resolution": result.data.get("resolution", ""),
    }


@app.post("/v1/video/generate")
async def generate_video(request: Request, api_key: str = _require_api_key) -> dict[str, Any]:
    body = await request.json()
    vid_request = {
        "prompt": body.get("prompt", ""),
        "duration_seconds": body.get("duration_seconds", 5),
        "resolution": body.get("resolution", "1080p"),
    }
    result = await router.route(
        capability=ProviderCapability.VIDEO_GENERATE,
        request=vid_request,
        channel_id=body.get("channel_id"),
        task_type="video_generate",
    )
    return {
        "video_url": result.data.get("video_url", ""),
        "provider": result.provider_id,
        "duration_seconds": result.data.get("duration_seconds", 0),
    }


@app.get("/providers")
async def list_providers(api_key: str = _require_api_key) -> list[dict[str, Any]]:
    return router.list_providers()


@app.get("/providers/health")
async def get_provider_health(api_key: str = _require_api_key) -> dict[str, str]:
    return await router.health_check_all()


@app.get("/providers/{provider_id}/models")
async def list_provider_models(provider_id: str, api_key: str = _require_api_key) -> list[dict[str, Any]]:
    try:
        return router.list_models(provider_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/cost/usage")
async def get_usage_report(
    request: Request,
    api_key: str = _require_api_key,
) -> dict[str, Any]:
    from_timestamp = request.query_params.get("from")
    to_timestamp = request.query_params.get("to")
    channel_id = request.query_params.get("channel_id")

    from_ts = float(from_timestamp) if from_timestamp else None
    to_ts = float(to_timestamp) if to_timestamp else None

    return cost_tracker.get_usage_report(
        from_timestamp=from_ts,
        to_timestamp=to_ts,
        channel_id=channel_id,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("provider_gateway.main:app", host="0.0.0.0", port=8000, reload=False)
