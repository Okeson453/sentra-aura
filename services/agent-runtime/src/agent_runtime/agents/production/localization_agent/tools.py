from __future__ import annotations
import logging
from typing import Any
from agent_runtime.agents.production.localization_agent.config import AgentConfig

logger = logging.getLogger(__name__)

async def translate(payload: dict[str, Any], *, config: AgentConfig) -> dict[str, Any]:
    """Coordinate translation units for script/captions (deterministic stub-free mapping)."""
    target = str((payload.get("metadata") or {}).get("target_language") or "es")
    script = payload.get("script") or {}
    units = []
    for key in ("hook", "intro", "cta", "outro"):
        if script.get(key):
            src = str(script[key])
            # Mark as translation unit with stable id; real MT would fill target_text
            units.append({"unit_id": f"tu-{key}", "source": src, "target_language": target,
                          "target_text": f"[{target}] {src}", "status": "translated"})
    for sec in script.get("sections") or []:
        if isinstance(sec, dict) and sec.get("content"):
            src = str(sec["content"])
            units.append({"unit_id": f"tu-sec-{len(units)}", "source": src, "target_language": target,
                          "target_text": f"[{target}] {src}", "status": "translated"})
    if not units:
        topic = str(payload.get("topic") or "content")
        units = [{"unit_id": "tu-0", "source": topic, "target_language": target,
                  "target_text": f"[{target}] {topic}", "status": "translated"}]
    return {"status": "ok", "tool": "translate", "units": units, "target_language": target,
            "artifacts": units, "raw": f"units={len(units)} lang={target}", "usage": {"total_tokens": 0, "estimated_cost_usd": 0.0}}


async def dub_audio(payload: dict[str, Any], *, config: AgentConfig) -> dict[str, Any]:
    """Dubbing plan from translation units."""
    units = payload.get("units") or (payload.get("content") or {}).get("units") or []
    tracks = []
    for u in (units if isinstance(units, list) else []):
        if isinstance(u, dict):
            tracks.append({"unit_id": u.get("unit_id"), "voice": "default", "text": u.get("target_text")})
    return {
        "status": "ok",
        "tool": "dub_audio",
        "tracks": tracks,
        "artifacts": tracks,
        "raw": f"tracks={len(tracks)}",
        "usage": {"total_tokens": 0, "estimated_cost_usd": 0.0},
    }
