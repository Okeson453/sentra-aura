from __future__ import annotations
import logging
from typing import Any
from agent_runtime.agents.clipping.captioning_agent.config import AgentConfig

logger = logging.getLogger(__name__)

async def generate_captions(payload: dict[str, Any], *, config: AgentConfig) -> dict[str, Any]:
    """Word-timed captions from clip text / reframed segments."""
    segments = payload.get("reframed") or payload.get("clips") or []
    content = payload.get("content") or {}
    if not segments and content.get("reframed"):
        segments = content["reframed"]
    captions = []
    for i, seg in enumerate(segments if isinstance(segments, list) else []):
        if not isinstance(seg, dict):
            continue
        text = str(seg.get("text") or seg.get("transcript") or payload.get("topic") or "")
        words = text.split()
        t = float(seg.get("source_start") or 0.0)
        timings = []
        for w in words:
            dur = max(0.12, min(0.55, len(w) * 0.06))
            timings.append({"word": w, "start": round(t, 3), "end": round(t + dur, 3)})
            t += dur
        captions.append({
            "clip_id": seg.get("clip_id") or f"cap-{i}",
            "language": (payload.get("metadata") or {}).get("language") or "en",
            "words": timings,
            "plain_text": text,
        })
    if not captions:
        topic = str(payload.get("topic") or "Update")
        captions = [{"clip_id": "cap-0", "language": "en", "plain_text": topic,
                     "words": [{"word": w, "start": i * 0.3, "end": i * 0.3 + 0.25} for i, w in enumerate(topic.split())]}]
    return {"status": "ok", "tool": "generate_captions", "captions": captions, "artifacts": captions,
            "raw": f"captions={len(captions)}", "usage": {"total_tokens": 0, "estimated_cost_usd": 0.0}}
