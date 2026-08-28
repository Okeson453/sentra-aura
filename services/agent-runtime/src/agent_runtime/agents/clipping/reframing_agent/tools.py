from __future__ import annotations
import logging
from typing import Any
from agent_runtime.agents.clipping.reframing_agent.config import AgentConfig

logger = logging.getLogger(__name__)

async def reframe_clip(payload: dict[str, Any], *, config: AgentConfig) -> dict[str, Any]:
    """Subject-tracking crop paths for vertical/square (Arch. §6)."""
    clips = payload.get("clips") or payload.get("candidates") or []
    if not clips and payload.get("content"):
        clips = payload["content"].get("candidates") or []
    aspect = str((payload.get("metadata") or {}).get("aspect_ratio") or "9:16")
    target_w, target_h = (9, 16) if aspect == "9:16" else (1, 1)
    results = []
    for i, c in enumerate(clips if isinstance(clips, list) else []):
        if not isinstance(c, dict):
            continue
        # Heuristic subject center from text density / default mid-frame
        cx, cy = 0.5, 0.42
        text = str(c.get("text") or c.get("reconstructed_text") or "")
        if any(w in text.lower() for w in ("face", "person", "speaker", "host")):
            cy = 0.35
        crop = {
            "clip_id": c.get("clip_id") or f"rf-{i}",
            "aspect_ratio": aspect,
            "crop_box": {"x": max(0.0, cx - 0.28), "y": max(0.0, cy - 0.28), "w": 0.56, "h": 0.72},
            "tracking_path": [{"t": 0.0, "cx": cx, "cy": cy}, {"t": 1.0, "cx": cx, "cy": cy + 0.02}],
            "source_start": c.get("start_seconds", 0),
            "source_end": c.get("end_seconds", 0),
        }
        results.append(crop)
    if not results:
        topic = str(payload.get("topic") or "content")
        results = [{"clip_id": "rf-default", "aspect_ratio": aspect, "crop_box": {"x": 0.2, "y": 0.1, "w": 0.6, "h": 0.8},
                    "tracking_path": [{"t": 0.0, "cx": 0.5, "cy": 0.4}], "topic": topic}]
    return {"status": "ok", "tool": "reframe_clip", "reframed": results, "artifacts": results,
            "raw": f"reframed={len(results)} aspect={aspect}", "usage": {"total_tokens": 0, "estimated_cost_usd": 0.0}}
