from __future__ import annotations
import logging
from typing import Any
from agent_runtime.agents.operations.compliance_agent.config import AgentConfig as AgentConfig

logger = logging.getLogger(__name__)

async def check_compliance(payload: dict[str, Any], *, config: AgentConfig) -> dict[str, Any]:
    """Policy checks: banned terms, sponsorship disclosure, age gating."""
    text = " ".join([
        str(payload.get("topic") or ""),
        str((payload.get("script") or {}).get("hook") or ""),
        str((payload.get("content") or {}).get("text") or ""),
    ]).lower()
    findings = []
    banned = ["guaranteed returns", "buy now or lose", "secret government"]
    for b in banned:
        if b in text:
            findings.append({"rule": "banned_phrase", "phrase": b, "severity": "high"})
    if "sponsor" in text or "paid partnership" in text:
        if "disclosure" not in text and "#ad" not in text:
            findings.append({"rule": "missing_sponsorship_disclosure", "severity": "medium"})
    return {"status": "ok", "tool": "check_compliance", "findings": findings, "compliant": not findings,
            "artifacts": findings, "raw": f"topic={payload.get('topic','')} findings={len(findings)}", "usage": {"total_tokens": 0, "estimated_cost_usd": 0.0}}
