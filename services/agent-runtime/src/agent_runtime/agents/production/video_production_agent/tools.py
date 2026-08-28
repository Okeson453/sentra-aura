from __future__ import annotations

import logging
from typing import Any

import httpx

from agent_runtime.agents.production.video_production_agent.config import AgentConfig as AgentConfig

logger = logging.getLogger(__name__)


async def assemble_timeline(payload: dict[str, Any], *, config: AgentConfig) -> dict[str, Any]:
    """Build an EDL-style timeline from shots/script for media-renderer."""
    shots = payload.get("shots") or (payload.get("content") or {}).get("shots") or []
    script = payload.get("script") or {}
    timeline = []
    t = 0.0
    if shots:
        for i, s in enumerate(shots if isinstance(shots, list) else []):
            if not isinstance(s, dict):
                continue
            dur = float(s.get("duration_seconds") or 5.0)
            timeline.append({
                "idx": i,
                "shot_id": s.get("shot_id") or f"sh-{i}",
                "in": t,
                "out": t + dur,
                "visual_asset_id": s.get("visual_asset_id"),
            })
            t += dur
    else:
        for key in ("hook", "intro", "cta"):
            if script.get(key):
                timeline.append({
                    "idx": len(timeline),
                    "shot_id": key,
                    "in": t,
                    "out": t + 5.0,
                    "text": str(script[key])[:80],
                })
                t += 5.0
    if not timeline:
        timeline = [{"idx": 0, "shot_id": "main", "in": 0.0, "out": 30.0, "topic": payload.get("topic")}]
    return {
        "status": "ok",
        "tool": "assemble_timeline",
        "timeline": timeline,
        "duration": t or 30.0,
        "artifacts": timeline,
        "raw": f"clips={len(timeline)} duration={t}",
        "usage": {"total_tokens": 0, "estimated_cost_usd": 0.0},
    }


async def render_video(payload: dict[str, Any], *, config: AgentConfig) -> dict[str, Any]:
    """Submit timeline to media-renderer for actual render job creation."""
    timeline = payload.get("timeline") or (payload.get("content") or {}).get("timeline") or []
    base = (getattr(config, "media_renderer_url", None) or "http://localhost:8000").rstrip("/")
    topic = str(payload.get("topic") or "")
    render_job: dict[str, Any] = {
        "format": "mp4",
        "timeline_clips": len(timeline) if isinstance(timeline, list) else 0,
        "topic": topic,
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(getattr(config, "timeout_seconds", 60.0), connect=5.0)) as client:
            body = {
                "timeline": timeline,
                "format": "mp4",
                "topic": topic,
                "channel_id": (payload.get("metadata") or {}).get("channel_id") or "default",
            }
            # REAL_INTEGRATION: media-renderer
            r = await client.post(
                f"{base}/render",
                headers={"Authorization": "Bearer dev-token"},
                json=body,
            )
            if r.status_code < 400:
                data = r.json() if r.content else {}
                render_job.update({
                    "job_id": data.get("job_id") or data.get("id"),
                    "status": data.get("status") or "queued",
                    "service_response": data,
                })
            else:
                logger.warning("media-renderer status %s: %s", r.status_code, r.text[:200])
                render_job["status"] = f"rejected_{r.status_code}"
                render_job["error"] = r.text[:300]
    except Exception as exc:
        logger.warning("media-renderer unreachable: %s", exc)
        render_job["status"] = "unreachable"
        render_job["error"] = str(exc)

    return {
        "status": "ok" if render_job.get("status") not in ("unreachable",) else "degraded",
        "tool": "render_video",
        "render_job": render_job,
        "artifacts": [render_job],
        "raw": f"render_clips={render_job.get('timeline_clips')} status={render_job.get('status')}",
        "usage": {"total_tokens": 0, "estimated_cost_usd": 0.0},
    }
