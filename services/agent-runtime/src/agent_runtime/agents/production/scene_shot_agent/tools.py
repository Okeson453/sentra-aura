from __future__ import annotations
import json, logging, re
from typing import Any
import httpx
from agent_runtime.agents.production.scene_shot_agent.config import AgentConfig

logger = logging.getLogger(__name__)

def try_parse_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        try:
            return json.loads(fence.group(1))
        except json.JSONDecodeError:
            pass
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    return None

async def complete(prompt: str, *, config: AgentConfig) -> dict[str, Any]:
    url = f"{config.provider_gateway_url.rstrip('/')}/v1/complete"
    payload = {"prompt": prompt, "model": config.default_model, "temperature": 0.3, "max_tokens": 2000}
    async with httpx.AsyncClient(timeout=httpx.Timeout(config.timeout_seconds, connect=10.0)) as http:
        r = await http.post(url, json=payload)
        r.raise_for_status()
        return r.json()

async def plan_shots(
    script: dict[str, Any],
    visual_assets: list[dict[str, Any]] | None = None,
    *,
    config: AgentConfig,
) -> dict[str, Any]:
    """Matrix tool: plan_shots — scene/shot list via provider-gateway."""
    visual_assets = visual_assets or []
    sections: list[tuple[str, str]] = []
    for key in ("hook", "intro", "cta", "outro"):
        if script.get(key):
            sections.append((key, str(script[key])[:200]))
    for i, sec in enumerate(script.get("sections") or []):
        if isinstance(sec, dict):
            sections.append((str(sec.get("title") or f"s{i}"), str(sec.get("content") or "")[:200]))
        elif isinstance(sec, str) and sec.strip():
            sections.append((f"s{i}", sec[:200]))
    if not sections:
        sections = [("main", "default scene")]

    prompt = (
        "You are the Scene/Shot Agent. Plan cinematic shots as JSON "
        '{"shots":[{"shot_id":"...","scene_id":"...","description":"...","duration_seconds":5,"camera":"medium"}]}.\n'
        f"Script sections: {json.dumps(sections)}\n"
        f"Visual asset ids available: {[a.get('asset_id') for a in visual_assets if isinstance(a, dict)]}\n"
    )
    data = await complete(prompt, config=config)
    text = data.get("text") or data.get("content") or ""
    usage = data.get("usage") or {}
    parsed = try_parse_json_object(text) or {}
    provider_shots = parsed.get("shots") or []
    out: list[dict[str, Any]] = []
    for i, (sid, desc) in enumerate(sections):
        asset = None
        if i < len(visual_assets) and isinstance(visual_assets[i], dict):
            asset = visual_assets[i].get("asset_id")
        if i < len(provider_shots) and isinstance(provider_shots[i], dict):
            s = provider_shots[i]
            out.append({
                "shot_id": str(s.get("shot_id") or f"shot-{i}"),
                "scene_id": str(s.get("scene_id") or sid),
                "description": str(s.get("description") or desc),
                "duration_seconds": float(s.get("duration_seconds") or 5),
                "visual_asset_id": s.get("visual_asset_id") or asset,
                "camera": str(s.get("camera") or "medium"),
            })
        else:
            out.append({
                "shot_id": f"shot-{i}",
                "scene_id": sid,
                "description": desc,
                "duration_seconds": 5.0,
                "visual_asset_id": asset,
                "camera": "medium",
            })
    return {
        "shots": out,
        "raw_text": text,
        "usage": {
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
            "estimated_cost_usd": float(usage.get("estimated_cost_usd") or 0.0),
        },
    }
