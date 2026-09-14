"""Temporal activities for SentraAura.

Matches Architecture §4.1, §5.1.
These activities perform the actual work of the autonomous loop.
"""
from __future__ import annotations

import logging

import httpx
from typing import Any

from sentinel_security import create_service_token
from temporalio import activity

from orchestrator.config import _INSECURE_JWT_DEFAULTS, get_settings

logger = logging.getLogger(__name__)

# Configuration for service endpoints
SERVICES = {
    "research-service": "http://research-service:8000",
    "agent-runtime": "http://agent-runtime:8000",
    "clipping-engine": "http://clipping-engine:8000",
    "publishing-service": "http://publishing-service:8000",
    "analytics-ingestion": "http://analytics-ingestion:8000",
    "media-renderer": "http://media-renderer:8000",
    "provider-gateway": "http://provider-gateway:8000",
    "policy-engine": "http://policy-engine:8000",
}

async def _call_service(service_name: str, endpoint: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Call an internal service with retry logic.

    The service must exist in the SERVICES map: a missing entry is a configuration
    defect, not a reason to silently retarget the call at localhost:8000 (which
    would produce a connection error that is indistinguishable from a real outage).
    """
    base = SERVICES.get(service_name)
    if base is None:
        raise ValueError(
            f"Unknown service '{service_name}' in _call_service; "
            f"known services: {sorted(SERVICES)}"
        )
    url = f"{base}{endpoint}"
    settings = get_settings()
    signing_secret = settings.jwt_secret
    if settings.environment != "development" and (
        not signing_secret or signing_secret in _INSECURE_JWT_DEFAULTS
    ):
        raise RuntimeError(
            "A secure JWT_SECRET is required for authenticated internal service calls"
        )

    token = create_service_token(
        settings.service_name,
        roles=["service"],
        secret=signing_secret,
        ttl_seconds=settings.service_auth_token_ttl_seconds,
        algorithm=settings.jwt_algorithm,
    )
    headers = {
        "Authorization": f"Bearer {token}",
        # Provider Gateway currently uses its service credential through this
        # header, while JWT-protected services consume Authorization.
        settings.api_key_header: signing_secret,
    }

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(settings.service_request_timeout_seconds),
        headers=headers,
    ) as client:
        try:
            if payload is not None:
                response = await client.post(url, json=payload)
            else:
                response = await client.get(url)
            response.raise_for_status()
            if not response.content:
                return {}
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError(
                    f"Service {service_name} returned non-object JSON at {endpoint}: {type(data).__name__}"
                )
            return data
        except httpx.HTTPStatusError as e:
            logger.error(f"Service {service_name} call failed: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Service {service_name} call error: {str(e)}")
            raise


async def _call_service_or_raise(
    service_name: str,
    endpoint: str,
    payload: dict[str, Any],
    *,
    activity_name: str,
    default_status: str = "failed",
    **extra: Any,
) -> dict[str, Any]:
    """Call a service, keeping the existing activity-shaped result contract.

    On success the service response is merged into a result dict carrying
    ``status="completed"`` and any caller-supplied extra fields. On failure the
    activity raises instead of returning a ``status="failed"`` dict: returning a
    failure dict lets Temporal replay mark the activity COMPLETED, so workflow
    retry policies and crash-recovery never engage and a broken dependency is
    silently reported to the caller as a success.
    """
    try:
        result = await _call_service(service_name, endpoint, payload)
    except Exception as exc:
        logger.error(f"{activity_name} failed: {exc}")
        raise
    out: dict[str, Any] = dict(extra)
    out.update(result)
    out["status"] = "completed"
    return out


def _project(result: dict[str, Any], mapping: dict[str, str], *, defaults: dict[str, Any]) -> dict[str, Any]:
    """Copy selected service response keys into activity result field names.

    ``mapping`` maps a result field name to the response key it is read from.
    Missing keys fall back to ``defaults`` so the activity result shape stays
    stable for existing callers.
    """
    out: dict[str, Any] = {}
    for dest, source in mapping.items():
        out[dest] = result.get(source, defaults.get(dest))
    return out


@activity.defn
async def execute_agent_task(task_type: str, agent_type: str, inputs: dict[str, Any]) -> dict[str, Any]:
    """Execute a single agent task by calling the agent-runtime service."""
    payload = {
        "task_type": task_type,
        "agent_type": agent_type,
        "inputs": inputs,
    }
    result = await _call_service_or_raise(
        "agent-runtime",
        "/v1/execute",
        payload,
        activity_name="execute_agent_task",
        task_type=task_type,
        agent_type=agent_type,
    )
    return {
        "task_type": task_type,
        "agent_type": agent_type,
        "status": "completed",
        "outputs": result.get("outputs", {}),
    }


@activity.defn
async def research_topic(channel_id: str, topic: str) -> dict[str, Any]:
    """Research a topic by calling the research-service."""
    payload = {
        "channel_id": channel_id,
        "topic": topic,
    }
    result = await _call_service_or_raise(
        "research-service",
        "/research",
        payload,
        activity_name="research_topic",
        channel_id=channel_id,
        topic=topic,
    )
    return {
        "channel_id": channel_id,
        "topic": topic,
        "sources": result.get("sources", []),
        "claims": result.get("claims", []),
        "status": "completed",
    }


@activity.defn
async def draft_script(channel_id: str, research: dict[str, Any]) -> dict[str, Any]:
    """Draft a script by calling the agent-runtime service."""
    payload = {
        "channel_id": channel_id,
        "research": research,
    }
    result = await _call_service_or_raise(
        "agent-runtime",
        "/v1/draft-script",
        payload,
        activity_name="draft_script",
        channel_id=channel_id,
    )
    return {
        "channel_id": channel_id,
        "script_id": result.get("script_id", ""),
        "title": result.get("title", research.get("topic", "")),
        "content": result.get("content", ""),
        "status": "completed",
    }


@activity.defn
async def produce_voice(channel_id: str, script: dict[str, Any]) -> dict[str, Any]:
    """Produce voice narration by calling the provider-gateway."""
    payload = {
        "channel_id": channel_id,
        "script_id": script.get("script_id", ""),
        "text": script.get("content", ""),
        "voice": "default",
    }
    result = await _call_service_or_raise(
        "provider-gateway",
        "/v1/tts",
        payload,
        activity_name="produce_voice",
        channel_id=channel_id,
        script_id=script.get("script_id", ""),
    )
    return {
        "channel_id": channel_id,
        "script_id": script.get("script_id", ""),
        "audio_url": result.get("audio_url", ""),
        "status": "completed",
    }


@activity.defn
async def generate_visuals(channel_id: str, script: dict[str, Any]) -> dict[str, Any]:
    """Generate visuals by calling the provider-gateway."""
    payload = {
        "channel_id": channel_id,
        "script_id": script.get("script_id", ""),
        "prompt": script.get("content", ""),
        "count": 5,
    }
    result = await _call_service_or_raise(
        "provider-gateway",
        "/v1/images/generate",
        payload,
        activity_name="generate_visuals",
        channel_id=channel_id,
        script_id=script.get("script_id", ""),
    )
    return {
        "channel_id": channel_id,
        "script_id": script.get("script_id", ""),
        "assets": result.get("image_urls", []),
        "status": "completed",
    }


@activity.defn
async def render_video(channel_id: str, script: dict[str, Any], voice: dict[str, Any], visuals: dict[str, Any]) -> dict[str, Any]:
    """Render a video by calling the media-renderer service."""
    payload = {
        "channel_id": channel_id,
        "script_id": script.get("script_id", ""),
        "audio_url": voice.get("audio_url", ""),
        "visual_assets": visuals.get("assets", []),
        "format": "mp4",
    }
    result = await _call_service_or_raise(
        "media-renderer",
        "/render",
        payload,
        activity_name="render_video",
        channel_id=channel_id,
    )
    return {
        "channel_id": channel_id,
        "video_id": result.get("job_id", ""),
        "render_job_id": result.get("job_id", ""),
        "status": "completed",
        "output_url": result.get("output_url", ""),
    }


@activity.defn
async def generate_clips(channel_id: str, video_id: str, script: dict[str, Any]) -> dict[str, Any]:
    """Generate clips by calling the clipping-engine service."""
    payload = {
        "channel_id": channel_id,
        "video_id": video_id,
        "script": script,
    }
    result = await _call_service_or_raise(
        "clipping-engine",
        "/clips/detect",
        payload,
        activity_name="generate_clips",
        channel_id=channel_id,
        video_id=video_id,
    )
    return {
        "channel_id": channel_id,
        "video_id": video_id,
        "candidates": result.get("candidates", []),
        "status": "completed",
    }


@activity.defn
async def publish_content(channel_id: str, video_id: str, clips: dict[str, Any], script: dict[str, Any]) -> dict[str, Any]:
    """Publish content by calling the publishing-service."""
    # Create publication for the main video
    video_pub = {
        "channel_id": channel_id,
        "asset_id": video_id,
        "title": script.get("title", ""),
        "description": script.get("content", "")[:500],
        "platforms": ["youtube"],
        "tags": script.get("tags", []),
    }
    
    try:
        video_result = await _call_service("publishing-service", "/publications", video_pub)
        video_publication_id = video_result.get("publication_id")

        # Request publication on the external platform. Without this call the
        # publication record stays in its initial state and nothing is ever sent
        # to YouTube.
        if video_publication_id:
            video_result = await _call_service(
                "publishing-service", f"/publications/{video_publication_id}/publish", {}
            )

        # Publish each clip. A clip that fails to publish must not be counted as
        # successful: it is recorded as failed so the caller can reconcile.
        clip_results = []
        for candidate in clips.get("candidates", [])[:5]:  # Limit to top 5 clips
            clip_pub = {
                "channel_id": channel_id,
                "asset_id": candidate.get("clip_id", ""),
                "title": candidate.get("title", script.get("title", "")),
                "description": f"Clip from: {script.get('title', '')}",
                "platforms": ["youtube"],
                "tags": ["clip", "short"],
            }
            clip_id = candidate.get("clip_id", "")
            try:
                clip_result = await _call_service("publishing-service", "/publications", clip_pub)
                clip_publication_id = clip_result.get("publication_id")
                if clip_publication_id:
                    clip_result = await _call_service(
                        "publishing-service", f"/publications/{clip_publication_id}/publish", {}
                    )
                clip_results.append(clip_result)
            except Exception as e:
                logger.warning(f"Failed to publish clip {clip_id}: {e}")
                clip_results.append({"clip_id": clip_id, "status": "failed", "error": str(e)})

        published_any = bool(video_publication_id)
        return {
            "channel_id": channel_id,
            "video_id": video_id,
            "video_publication_id": video_publication_id,
            "video_status": video_result.get("status"),
            "clip_count": len(clip_results),
            "clip_results": clip_results,
            "status": "completed" if published_any else "failed",
            "error": None if published_any else "publishing-service returned no publication_id",
        }
    except Exception as exc:
        logger.error(f"Publishing failed: {exc}")
        raise


@activity.defn
async def record_analytics(channel_id: str, video_id: str, publish_result: dict[str, Any], clips: dict[str, Any]) -> dict[str, Any]:
    """Record analytics by calling the analytics-ingestion service."""
    payload = {
        "channel_id": channel_id,
        "video_id": video_id,
        "publish_result": publish_result,
        "clips": clips,
        "event_type": "publication_complete",
    }
    result = await _call_service_or_raise(
        "analytics-ingestion",
        "/api/v1/tasks/status",
        payload,
        activity_name="record_analytics",
        channel_id=channel_id,
        video_id=video_id,
    )
    return {
        "channel_id": channel_id,
        "video_id": video_id,
        "event_id": result.get("event_id", ""),
        "status": "completed",
    }


@activity.defn
async def update_learning(channel_id: str, video_id: str, analytics_result: dict[str, Any], clips: dict[str, Any]) -> dict[str, Any]:
    """Update learning models by calling the analytics-ingestion service."""
    # Trigger signal computation over the persisted metrics history so the
    # feedback path reaches the learning layer rather than a nonexistent route.
    result = await _call_service_or_raise(
        "analytics-ingestion",
        "/api/v1/signals",
        {"metrics_history": [analytics_result]},
        activity_name="update_learning",
        channel_id=channel_id,
        video_id=video_id,
    )
    return {
        "channel_id": channel_id,
        "video_id": video_id,
        "insights": result.get("insights", []),
        "signals": result,
        "status": "completed",
    }


@activity.defn
async def optimize_policy(channel_id: str, learning_result: dict[str, Any], analytics_result: dict[str, Any]) -> dict[str, Any]:
    """Optimize policy by calling the policy-engine service."""
    payload = {
        "decision_id": f"optimize-{channel_id}-{learning_result.get('video_id', '')}",
        "channel_id": channel_id,
        "autonomy_level": learning_result.get("autonomy_level", "L1"),
        "context": {
            "learning": learning_result,
            "analytics": analytics_result,
        },
    }
    try:
        result = await _call_service("policy-engine", "/api/v1/evaluate", payload)
    except Exception as exc:
        logger.error(f"Policy optimization failed: {exc}")
        raise
    return {
        "channel_id": channel_id,
        "policy_version": result.get("policy_version", 1),
        "updates": result.get("risk_scores", []),
        "approved": result.get("approved"),
        "status": "completed",
    }
