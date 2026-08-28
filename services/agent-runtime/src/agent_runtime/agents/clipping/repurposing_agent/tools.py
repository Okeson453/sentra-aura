from __future__ import annotations
import logging
from typing import Any
from agent_runtime.agents.clipping.repurposing_agent.config import AgentConfig

logger = logging.getLogger(__name__)

async def build_derivatives(payload: dict[str, Any], *, config: AgentConfig) -> dict[str, Any]:
    """Platform-specific derivatives from captioned clips."""
    captions = payload.get("captions") or (payload.get("content") or {}).get("captions") or []
    platforms = (payload.get("metadata") or {}).get("platforms") or ["youtube_shorts", "tiktok", "instagram_reels"]
    derivatives = []
    for cap in (captions if isinstance(captions, list) else []):
        if not isinstance(cap, dict):
            continue
        for plat in platforms:
            derivatives.append({
                "clip_id": cap.get("clip_id"),
                "platform": plat,
                "max_duration": 60 if plat != "youtube_shorts" else 60,
                "caption_plain": (cap.get("plain_text") or "")[:220],
                "hashtags": ["#shorts"] if "youtube" in plat else ["#fyp", "#viral"][:2],
            })
    if not derivatives:
        topic = str(payload.get("topic") or "clip")
        derivatives = [{"clip_id": "der-0", "platform": "tiktok", "caption_plain": topic, "hashtags": ["#fyp"]}]
    return {"status": "ok", "tool": "build_derivatives", "derivatives": derivatives, "artifacts": derivatives,
            "raw": f"derivatives={len(derivatives)}", "usage": {"total_tokens": 0, "estimated_cost_usd": 0.0}}
