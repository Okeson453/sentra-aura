from __future__ import annotations
import hashlib
import logging
from typing import Any
import httpx
from agent_runtime.agents.creative.visual_asset_agent.config import VisualAssetConfig

logger = logging.getLogger(__name__)

async def generate_image(prompt: str, *, config: VisualAssetConfig, size: str | None = None) -> dict[str, Any]:
    """Permission tool: generate_image — provider-gateway POST /v1/images/generate."""
    url = f"{config.provider_gateway_url.rstrip('/')}/v1/images/generate"
    payload = {"prompt": prompt, "size": size or config.default_image_size}
    logger.info("generate_image → %s", url)
    async with httpx.AsyncClient(timeout=httpx.Timeout(config.timeout_seconds, connect=10.0)) as http:
        r = await http.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
    data.setdefault("image_url", data.get("url"))
    data.setdefault("provider", "provider-gateway")
    return data

async def edit_image(image_url: str, instruction: str, *, config: VisualAssetConfig) -> dict[str, Any]:
    """Permission tool: edit_image — re-generate with edit instruction (gateway image path)."""
    prompt = f"Edit image {image_url}: {instruction}"
    return await generate_image(prompt, config=config)

def scenes_from_request(scene_descriptions: list[str], script: dict[str, Any], budget: int) -> list[str]:
    scenes = list(scene_descriptions or [])
    if not scenes and script:
        for key in ("hook", "intro", "cta", "outro"):
            if script.get(key):
                scenes.append(str(script[key])[:200])
        for sec in script.get("sections") or []:
            if isinstance(sec, dict) and sec.get("content"):
                note = sec.get("b_roll_notes") or sec.get("title") or ""
                scenes.append(f"{sec.get('title','scene')}: {note or str(sec.get('content'))[:120]}")
            elif isinstance(sec, str):
                scenes.append(sec[:200])
    return scenes[: max(1, budget)]
