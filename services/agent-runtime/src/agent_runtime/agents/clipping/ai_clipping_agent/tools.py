"""AI Clipping tools — selection/rank/dedup over clipping-engine scores (Architecture §6)."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from agent_runtime.agents.clipping.ai_clipping_agent.config import AgentConfig
from agent_runtime.agents.clipping.ai_clipping_agent.scoring import rank_and_dedup

logger = logging.getLogger(__name__)


async def select_clips(payload: dict[str, Any], *, config: AgentConfig) -> dict[str, Any]:
    """Permission tool: select_clips.

    Pipeline (Arch. §6.1): request scored candidates from clipping-engine
    (service owns ClipScore), then rank/dedup/select at the agent layer.
    """
    topic = str(payload.get("topic") or "")
    video_id = str(payload.get("video_id") or "unknown")
    segments = payload.get("segments") or []
    if not segments and payload.get("script"):
        # Synthetic segments from script when engine has no ASR input yet
        script = payload["script"] if isinstance(payload["script"], dict) else {}
        text = str(script.get("hook") or topic)
        segments = [{
            "segment_id": "s0",
            "start_seconds": 0,
            "end_seconds": 20,
            "text": text,
            "visual_change": 0.5,
        }]

    threshold = float(payload.get("score_threshold") or getattr(config, "score_threshold", 0.35) or 0.35)
    max_clips = int(payload.get("max_clips") or getattr(config, "max_clips", 5) or 5)
    base = (getattr(config, "clipping_engine_url", None) or "http://localhost:8000").rstrip("/")

    candidates: list[dict[str, Any]] = []
    segment_count = len(segments) if isinstance(segments, list) else 0
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(getattr(config, "timeout_seconds", 60.0), connect=5.0)) as client:
            # REAL_INTEGRATION: clipping-engine
            r = await client.post(
                f"{base}/clips/detect",
                headers={"Authorization": "Bearer dev-token"},
                json={
                    "video_id": video_id,
                    "topic": topic,
                    "segments": segments,
                    "max_clips": max_clips,
                },
            )
            r.raise_for_status()
            job = r.json()
            job_id = job.get("job_id")
            # Prefer inline candidates from completed detect; else fetch results
            if job.get("candidates"):
                candidates = list(job["candidates"])
            elif job_id:
                # REAL_INTEGRATION: clipping-engine
                r2 = await client.get(
                    f"{base}/clips/jobs/{job_id}/results",
                    headers={"Authorization": "Bearer dev-token"},
                )
                if r2.status_code < 400:
                    body = r2.json()
                    candidates = list(body.get("candidates") or [])
                    segment_count = int(body.get("segment_count") or segment_count)
            segment_count = int(job.get("segment_count") or segment_count)
    except Exception as exc:
        logger.warning("clipping-engine call failed: %s", exc)
        return {
            "status": "error",
            "tool": "select_clips",
            "error": str(exc),
            "candidates": [],
            "rejected": [],
            "segment_count": segment_count,
            "artifacts": [],
            "raw": f"engine_error={exc}",
            "usage": {"total_tokens": 0, "estimated_cost_usd": 0.0},
        }

    selected, rejected = rank_and_dedup(candidates, max_clips=max_clips, score_threshold=threshold)
    return {
        "status": "ok",
        "tool": "select_clips",
        "video_id": video_id,
        "candidates": selected,
        "rejected": rejected,
        "segment_count": segment_count,
        "artifacts": selected,
        "raw": f"topic={topic} selected={len(selected)} rejected={len(rejected)}",
        "usage": {"total_tokens": 0, "estimated_cost_usd": 0.0},
    }
