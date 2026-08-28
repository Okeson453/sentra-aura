from __future__ import annotations

import logging
from typing import Any

import httpx

from agent_runtime.agents.distribution.publishing_agent.config import AgentConfig as AgentConfig

logger = logging.getLogger(__name__)


async def publish_content(payload: dict[str, Any], *, config: AgentConfig) -> dict[str, Any]:
    """Build and submit platform publish payloads via publishing-service."""
    topic = str(payload.get("topic") or "")
    seo = payload.get("seo") or payload.get("content") or {}
    platforms = (payload.get("metadata") or {}).get("platforms") or ["youtube"]
    packages = []
    for plat in platforms:
        packages.append({
            "platform": plat,
            "title": (seo.get("titles") or [topic])[0] if isinstance(seo.get("titles"), list) else topic,
            "description": seo.get("description") or topic,
            "tags": seo.get("tags") or [],
            "visibility": "private",
            "status": "ready_to_submit",
        })

    service_url = getattr(config, "publishing_service_url", None) or ""
    submitted: list[dict[str, Any]] = []
    if service_url:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(getattr(config, "timeout_seconds", 30.0), connect=5.0)) as client:
                for pkg in packages:
                    body = {
                        "platform": pkg["platform"],
                        "title": pkg["title"],
                        "description": pkg["description"],
                        "tags": pkg["tags"],
                        "visibility": pkg["visibility"],
                        "channel_id": (payload.get("metadata") or {}).get("channel_id") or "default",
                    }
                    # REAL_INTEGRATION: publishing-service
                    r = await client.post(f"{service_url.rstrip('/')}/publications", json=body)
                    if r.status_code < 400:
                        submitted.append(r.json() if r.content else {"status": "created", **pkg})
                    else:
                        logger.warning("publishing-service rejected package: %s", r.status_code)
                        submitted.append({**pkg, "service_status": r.status_code})
        except Exception as exc:
            logger.warning("publishing-service unreachable, local packages only: %s", exc)

    return {
        "status": "ok",
        "tool": "publish_content",
        "packages": packages,
        "submitted": submitted,
        "artifacts": packages,
        "raw": f"packages={len(packages)} submitted={len(submitted)}",
        "usage": {"total_tokens": 0, "estimated_cost_usd": 0.0},
    }
