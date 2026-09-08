"""Temporal activities for SentraAura.

Matches Architecture §4.1, §5.1.
These activities perform the actual work of the autonomous loop.
"""
from __future__ import annotations

import httpx
import logging
from typing import Any

from temporalio import activity

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
}

async def _call_service(service_name: str, endpoint: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Call an internal service with retry logic."""
    url = f"{SERVICES.get(service_name, 'http://localhost:8000')}{endpoint}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if payload:
                response = await client.post(url, json=payload)
            else:
                response = await client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Service {service_name} call failed: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Service {service_name} call error: {str(e)}")
            raise


@activity.defn
async def execute_agent_task(task_type: str, agent_type: str, inputs: dict[str, Any]) -> dict[str, Any]:
    """Execute a single agent task by calling the agent-runtime service."""
    payload = {
        "task_type": task_type,
        "agent_type": agent_type,
        "inputs": inputs,
    }
    try:
        result = await _call_service("agent-runtime", "/v1/execute", payload)
        return {
            "task_type": task_type,
            "agent_type": agent_type,
            "status": "completed",
            "outputs": result.get("outputs", {}),
        }
    except Exception as exc:
        logger.error(f"Agent task execution failed: {exc}")
        return {
            "task_type": task_type,
            "agent_type": agent_type,
            "status": "failed",
            "error": str(exc),
        }


@activity.defn
async def research_topic(channel_id: str, topic: str) -> dict[str, Any]:
    """Research a topic by calling the research-service."""
    payload = {
        "channel_id": channel_id,
        "topic": topic,
    }
    try:
        result = await _call_service("research-service", "/v1/research", payload)
        return {
            "channel_id": channel_id,
            "topic": topic,
            "sources": result.get("sources", []),
            "claims": result.get("claims", []),
            "status": "completed",
        }
    except Exception as exc:
        logger.error(f"Research failed: {exc}")
        return {
            "channel_id": channel_id,
            "topic": topic,
            "sources": [],
            "claims": [],
            "status": "failed",
            "error": str(exc),
        }


@activity.defn
async def draft_script(channel_id: str, research: dict[str, Any]) -> dict[str, Any]:
    """Draft a script by calling the agent-runtime service."""
    payload = {
        "channel_id": channel_id,
        "research": research,
    }
    try:
        result = await _call_service("agent-runtime", "/v1/draft-script", payload)
        return {
            "channel_id": channel_id,
            "script_id": result.get("script_id", ""),
            "title": result.get("title", research.get("topic", "")),
            "content": result.get("content", ""),
            "status": "completed",
        }
    except Exception as exc:
        logger.error(f"Script drafting failed: {exc}")
        return {
            "channel_id": channel_id,
            "script_id": "",
            "title": research.get("topic", ""),
            "content": "",
            "status": "failed",
            "error": str(exc),
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
    try:
        result = await _call_service("provider-gateway", "/v1/tts", payload)
        return {
            "channel_id": channel_id,
            "script_id": script.get("script_id", ""),
            "audio_url": result.get("audio_url", ""),
            "status": "completed",
        }
    except Exception as exc:
        logger.error(f"Voice production failed: {exc}")
        return {
            "channel_id": channel_id,
            "script_id": script.get("script_id", ""),
            "audio_url": "",
            "status": "failed",
            "error": str(exc),
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
    try:
        result = await _call_service("provider-gateway", "/v1/images/generate", payload)
        return {
            "channel_id": channel_id,
            "script_id": script.get("script_id", ""),
            "assets": result.get("image_urls", []),
            "status": "completed",
        }
    except Exception as exc:
        logger.error(f"Visual generation failed: {exc}")
        return {
            "channel_id": channel_id,
            "script_id": script.get("script_id", ""),
            "assets": [],
            "status": "failed",
            "error": str(exc),
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
    try:
        result = await _call_service("media-renderer", "/render", payload)
        return {
            "channel_id": channel_id,
            "video_id": result.get("job_id", ""),
            "render_job_id": result.get("job_id", ""),
            "status": "completed",
            "output_url": result.get("output_url", ""),
        }
    except Exception as exc:
        logger.error(f"Video rendering failed: {exc}")
        return {
            "channel_id": channel_id,
            "video_id": "",
            "render_job_id": "",
            "status": "failed",
            "error": str(exc),
        }


@activity.defn
async def generate_clips(channel_id: str, video_id: str, script: dict[str, Any]) -> dict[str, Any]:
    """Generate clips by calling the clipping-engine service."""
    payload = {
        "channel_id": channel_id,
        "video_id": video_id,
        "script": script,
    }
    try:
        result = await _call_service("clipping-engine", "/clips/detect", payload)
        return {
            "channel_id": channel_id,
            "video_id": video_id,
            "candidates": result.get("candidates", []),
            "status": "completed",
        }
    except Exception as exc:
        logger.error(f"Clip generation failed: {exc}")
        return {
            "channel_id": channel_id,
            "video_id": video_id,
            "candidates": [],
            "status": "failed",
            "error": str(exc),
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
        
        # Publish each clip
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
            try:
                clip_result = await _call_service("/publications", clip_pub)
                clip_results.append(clip_result)
            except Exception as e:
                logger.warning(f"Failed to publish clip {candidate.get('clip_id')}: {e}")
                clip_results.append({"status": "failed", "error": str(e)})
        
        return {
            "channel_id": channel_id,
            "video_id": video_id,
            "video_publication_id": video_result.get("publication_id"),
            "video_status": video_result.get("status"),
            "clip_count": len(clip_results),
            "clip_results": clip_results,
            "status": "completed",
        }
    except Exception as exc:
        logger.error(f"Publishing failed: {exc}")
        return {
            "channel_id": channel_id,
            "video_id": video_id,
            "status": "failed",
            "error": str(exc),
        }


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
    try:
        result = await _call_service("analytics-ingestion", "/v1/events", payload)
        return {
            "channel_id": channel_id,
            "video_id": video_id,
            "event_id": result.get("event_id", ""),
            "status": "completed",
        }
    except Exception as exc:
        logger.error(f"Analytics recording failed: {exc}")
        return {
            "channel_id": channel_id,
            "video_id": video_id,
            "status": "failed",
            "error": str(exc),
        }


@activity.defn
async def update_learning(channel_id: str, video_id: str, analytics_result: dict[str, Any], clips: dict[str, Any]) -> dict[str, Any]:
    """Update learning models by calling the analytics-ingestion service."""
    payload = {
        "channel_id": channel_id,
        "video_id": video_id,
        "analytics": analytics_result,
        "clips": clips,
        "event_type": "learning_update",
    }
    try:
        result = await _call_service("analytics-ingestion", "/v1/learning", payload)
        return {
            "channel_id": channel_id,
            "video_id": video_id,
            "insights": result.get("insights", []),
            "status": "completed",
        }
    except Exception as exc:
        logger.error(f"Learning update failed: {exc}")
        return {
            "channel_id": channel_id,
            "video_id": video_id,
            "status": "failed",
            "error": str(exc),
        }


@activity.defn
async def optimize_policy(channel_id: str, learning_result: dict[str, Any], analytics_result: dict[str, Any]) -> dict[str, Any]:
    """Optimize policy by calling the policy-engine service."""
    payload = {
        "channel_id": channel_id,
        "learning": learning_result,
        "analytics": analytics_result,
    }
    try:
        result = await _call_service("policy-engine", "/policies/optimize", payload)
        return {
            "channel_id": channel_id,
            "policy_version": result.get("policy_version", 1),
            "updates": result.get("updates", []),
            "status": "completed",
        }
    except Exception as exc:
        logger.error(f"Policy optimization failed: {exc}")
        return {
            "channel_id": channel_id,
            "status": "failed",
            "error": str(exc),
        }
