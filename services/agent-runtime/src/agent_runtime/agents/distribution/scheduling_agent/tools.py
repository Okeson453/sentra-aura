from __future__ import annotations
import logging
from typing import Any
from agent_runtime.agents.distribution.scheduling_agent.config import AgentConfig as AgentConfig

logger = logging.getLogger(__name__)

async def schedule_publish(payload: dict[str, Any], *, config: AgentConfig) -> dict[str, Any]:
    """Audience-timing + conflict avoidance (planning only — does not publish)."""
    topic = str(payload.get("topic") or "content")
    meta = payload.get("metadata") or {}
    platforms = meta.get("platforms") or ["youtube"]
    # Simple audience-hour peaks by region/platform heuristics
    peaks = {"youtube": [14, 18, 21], "tiktok": [12, 19, 22], "instagram": [11, 17, 20]}
    existing = meta.get("existing_slots") or []
    existing_hours = {int(s.get("hour", -1)) for s in existing if isinstance(s, dict)}
    slots = []
    for plat in platforms:
        for h in peaks.get(str(plat), [15, 19]):
            if h in existing_hours:
                continue  # conflict avoidance
            slots.append({"platform": plat, "hour_local": h, "reason": "audience_peak", "status": "planned"})
            break
        else:
            slots.append({"platform": plat, "hour_local": 16, "reason": "fallback", "status": "planned"})
    return {"status": "ok", "tool": "schedule_publish", "slots": slots, "planning_only": True,
            "artifacts": slots, "raw": f"topic={payload.get('topic','')} slots={len(slots)}", "usage": {"total_tokens": 0, "estimated_cost_usd": 0.0}}
