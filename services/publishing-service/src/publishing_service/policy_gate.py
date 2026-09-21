"""Governance gate for the publishing path.

Architecture (§9) requires that no content reaches an external platform without
a policy decision. Before this module existed, ``publishing-service`` had
**zero** references to ``policy-engine`` or ``rights-registry-service``: the
orchestrator evaluated policy *after* ``publish_content`` had already uploaded,
so the governance gate could observe a publication but could never prevent one.
A restrictive, absent or failed policy therefore had no effect on whether
content went live.

This gate is deliberately **fail-closed**:

* an unreachable or erroring policy-engine is a failure, not an implicit allow;
* a decision that carries no explicit ``approved: true`` is a denial;
* only an explicit deployment opt-out (``POLICY_GATE_ENABLED=false``) disables
  enforcement, and doing so is logged at WARNING so it is visible in an audit.

The decision is tenant-scoped: the request carries the acting tenant as a
*signed claim* on the service token, and policy-engine resolves the tenant from
that verified claim, so the gate cannot be steered by a caller-supplied id.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

#: Shown in audit logs when the gate is disabled by configuration.
_DISABLE_VALUES = frozenset({"0", "false", "no", "off"})

#: Autonomy level used for an unattended publish. L3 is the level the
#: architecture assigns to autonomous publishing with policy oversight.
DEFAULT_AUTONOMY_LEVEL = "L3"


class PolicyDenied(Exception):
    """Raised when the governance gate refuses a publication.

    Carries the decision document so the API can return a specific, auditable
    reason rather than a generic failure.
    """

    def __init__(self, message: str, decision: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.decision = decision or {}


def policy_engine_url() -> str:
    """Base URL of the governance service."""
    return os.environ.get("POLICY_ENGINE_URL", "http://policy-engine:8000").rstrip("/")


def policy_gate_enabled() -> bool:
    """Whether the governance gate is enforced.

    Defaults to **True**: a deployment that configures nothing still refuses to
    publish un-governed content. Only an explicit opt-out disables it.
    """
    return os.environ.get("POLICY_GATE_ENABLED", "true").strip().lower() not in _DISABLE_VALUES


def _signing_secret() -> str:
    """Secret used to sign the gate's service token.

    Read from the same ``JWT_SECRET`` the application uses; the deployment's
    config already refuses the insecure default in production.
    """
    return os.environ.get("JWT_SECRET", "change-me-in-production")


async def evaluate_publish_decision(
    *,
    tenant_id: str,
    channel_id: str,
    publication_id: str,
    autonomy_level: str = DEFAULT_AUTONOMY_LEVEL,
    context: dict[str, Any] | None = None,
    engine_url: str | None = None,
) -> dict[str, Any]:
    """Ask policy-engine whether this publication may proceed.

    Returns the governance decision document.

    Raises :class:`PolicyDenied` when the gate refuses the decision, and
    ``RuntimeError`` when the gate cannot be consulted at all. Callers must
    treat the ``RuntimeError`` as a denial: an un-evaluable policy is not an
    approval.
    """
    from sentinel_security import create_service_token

    url = f"{(engine_url or policy_engine_url()).rstrip('/')}/api/v1/evaluate"
    token = create_service_token(
        "publishing-service",
        roles=["service"],
        secret=_signing_secret(),
        tenant_id=tenant_id,
    )
    payload: dict[str, Any] = {
        "decision_id": f"publish-{publication_id}",
        "channel_id": channel_id,
        "tenant_id": tenant_id,
        "autonomy_level": autonomy_level,
        "context": {"publication_id": publication_id, **(context or {})},
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            response = await client.post(
                url, json=payload, headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            "policy gate rejected the decision request: "
            f"{exc.response.status_code} {exc.response.text}"
        ) from exc
    except Exception as exc:  # network, DNS, timeout
        raise RuntimeError(f"policy gate unreachable: {exc}") from exc

    decision = response.json()
    if not isinstance(decision, dict):
        raise RuntimeError(
            f"policy gate returned non-object JSON: {type(decision).__name__}"
        )
    return decision


async def require_publish_approval(
    *,
    tenant_id: str,
    channel_id: str,
    publication_id: str,
    autonomy_level: str = DEFAULT_AUTONOMY_LEVEL,
    context: dict[str, Any] | None = None,
    enabled: bool | None = None,
    engine_url: str | None = None,
) -> dict[str, Any]:
    """Enforce the governance gate for one publication.

    Returns the decision on an explicit approval. Raises :class:`PolicyDenied`
    on a refusal, and ``RuntimeError`` when the gate cannot be evaluated (the
    caller must not convert that into a success).
    """
    if not (policy_gate_enabled() if enabled is None else enabled):
        logger.warning(
            "policy_gate_disabled",
            extra={
                "publication_id": publication_id,
                "channel_id": channel_id,
                "tenant_id": tenant_id,
                "detail": "POLICY_GATE_ENABLED is false: publishing without a "
                "governance decision",
            },
        )
        return {"approved": None, "gate": "disabled"}

    decision = await evaluate_publish_decision(
        tenant_id=tenant_id,
        channel_id=channel_id,
        publication_id=publication_id,
        autonomy_level=autonomy_level,
        context=context,
        engine_url=engine_url,
    )

    if decision.get("approved") is not True:
        reason = (
            "policy gate returned no explicit approval: "
            f"approved={decision.get('approved')!r} "
            f"overall_risk={decision.get('overall_risk')!r} "
            f"requires_human_override={decision.get('requires_human_override')!r}"
        )
        logger.warning(
            "policy_gate_denied",
            extra={
                "publication_id": publication_id,
                "channel_id": channel_id,
                "tenant_id": tenant_id,
                "decision": decision,
            },
        )
        raise PolicyDenied(reason, decision)

    logger.info(
        "policy_gate_approved",
        extra={
            "publication_id": publication_id,
            "channel_id": channel_id,
            "tenant_id": tenant_id,
            "overall_risk": decision.get("overall_risk"),
            "policy_version": decision.get("policy_version"),
        },
    )
    return decision
