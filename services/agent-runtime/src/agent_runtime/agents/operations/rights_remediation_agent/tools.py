from __future__ import annotations

import logging
from typing import Any

from agent_runtime.agents.operations.rights_remediation_agent.config import AgentConfig as AgentConfig
from agent_runtime.agents.operations.rights_remediation_agent.rights_registry_client import (
    RightsRegistryClient,
)

logger = logging.getLogger(__name__)


async def remediate_rights(payload: dict[str, Any], *, config: AgentConfig) -> dict[str, Any]:
    """Detect rights conflicts via rights-registry-service and propose remediation."""
    assets = payload.get("assets") or (payload.get("content") or {}).get("assets") or []
    claims = payload.get("claims") or []
    conflicts: list[dict[str, Any]] = []
    registry_hits: list[dict[str, Any]] = []

    service_url = getattr(config, "rights_registry_url", None) or getattr(
        config, "rights_registry_service_url", None
    ) or ""
    if service_url:
        client = RightsRegistryClient(base_url=service_url, timeout=getattr(config, "timeout_seconds", 30.0))
        try:
            for a in (assets if isinstance(assets, list) else []):
                if not isinstance(a, dict):
                    continue
                rid = str(a.get("rights_id") or a.get("asset_id") or a.get("id") or "")
                if not rid:
                    continue
                try:
                    # REAL_INTEGRATION: rights-registry-service
                    hit = await client.acheck(rid)
                    registry_hits.append(hit if isinstance(hit, dict) else {"result": hit})
                    if isinstance(hit, dict) and hit.get("matched"):
                        conflicts.append({
                            "asset_id": rid,
                            "issue": "registry_matched_claim",
                            "remediation": "replace_or_mute",
                            "registry": hit,
                        })
                except Exception as exc:
                    logger.warning("rights check failed for %s: %s", rid, exc)
            await client.close()
        except Exception as exc:
            logger.warning("rights-registry-service unreachable: %s", exc)

    for a in (assets if isinstance(assets, list) else []):
        if not isinstance(a, dict):
            continue
        if a.get("license") in (None, "", "unknown") or a.get("claim_status") == "matched":
            conflicts.append({
                "asset_id": a.get("asset_id") or a.get("id"),
                "issue": "unlicensed_or_claimed",
                "remediation": "replace_or_mute" if a.get("claim_status") == "matched" else "obtain_license",
            })
    for cl in (claims if isinstance(claims, list) else []):
        if isinstance(cl, dict):
            conflicts.append({
                "asset_id": cl.get("asset_id"),
                "issue": "active_claim",
                "remediation": "dispute_or_replace",
            })

    return {
        "status": "ok",
        "tool": "remediate_rights",
        "conflicts": conflicts,
        "registry_hits": registry_hits,
        "artifacts": conflicts,
        "raw": f"conflicts={len(conflicts)} registry={len(registry_hits)}",
        "usage": {"total_tokens": 0, "estimated_cost_usd": 0.0},
    }
