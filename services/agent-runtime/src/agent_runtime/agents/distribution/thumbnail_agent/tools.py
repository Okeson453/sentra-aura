from __future__ import annotations
import logging
from typing import Any
from agent_runtime.agents.distribution.thumbnail_agent.config import AgentConfig

logger = logging.getLogger(__name__)

async def generate_thumbnail(payload: dict[str, Any], *, config: AgentConfig) -> dict[str, Any]:
    """Generate and score thumbnail candidates."""
    topic = str(payload.get("topic") or "Video")
    script = payload.get("script") or {}
    hook = str(script.get("hook") or topic)
    candidates = []
    styles = ["face_closeup_text", "bold_title_contrast", "before_after_split"]
    for i, style in enumerate(styles):
        # Score: text length, emotional words, contrast proxy
        emotion = 1.0 if any(w in hook.lower() for w in ("why", "secret", "never", "shocking", "?")) else 0.4
        score = min(1.0, 0.35 + 0.25 * emotion + 0.1 * (i == 0) + min(0.3, len(hook.split()) / 20.0))
        candidates.append({
            "candidate_id": f"thumb-{i}",
            "style": style,
            "title_text": hook[:48],
            "score": round(score, 3),
            "ctr_prior": round(0.02 + score * 0.08, 4),
        })
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return {"status": "ok", "tool": "generate_thumbnail", "candidates": candidates, "selected": candidates[0],
            "artifacts": candidates, "raw": f"thumbs={len(candidates)} best={candidates[0]['score']}",
            "usage": {"total_tokens": 0, "estimated_cost_usd": 0.0}}
