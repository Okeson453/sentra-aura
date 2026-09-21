"""Routes for the Policy Engine.

SECURITY: this service is the governance gate -- it decides whether a decision
may proceed to publication.  Every route therefore:

* authenticates the caller against the configured ``JWT_SECRET`` (the middleware
  rejects an unauthenticated request with 401 before the handler runs); and
* resolves the acting tenant from the **verified** token claim, never from a
  client-supplied header, query parameter or body (see
  ``sentinel_security.tenant``).

The channel a request names is treated as an assertion to verify: it is
compared against the authenticated tenant using a constant-time comparison, and
a mismatch is rejected with 403.  Reads are partitioned by tenant in the store,
so a channel id belonging to another tenant yields an empty result rather than
disclosing that tenant's policies.
"""
from __future__ import annotations

import hmac
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from sentinel_exceptions import AuthorizationError
from sentinel_security import auth_error_to_http_status, resolve_tenant_id

from policy_engine.config import get_settings
from policy_engine.engine import PolicyEngine
from policy_engine.models import AutonomyLevel, PolicyRule
from policy_engine.store import PolicyStore

logger = logging.getLogger(__name__)

router = APIRouter()

store = PolicyStore()

settings = get_settings()


def _require_tenant(request: Request, requested_tenant_id: str | None = None) -> str:
    """Resolve the tenant this request may act on.

    The tenant comes from the authenticated context placed on
    ``request.state.auth_context`` by ``service_kit``'s
    ``AuthenticationMiddleware``.  Never from a header/query/body.
    """
    auth_context = getattr(request.state, "auth_context", None)
    try:
        return resolve_tenant_id(
            auth_context,
            requested_tenant_id,
            enforce_isolation=getattr(settings, "enforce_tenant_isolation", True),
        )
    except AuthorizationError as exc:
        raise HTTPException(
            status_code=auth_error_to_http_status(exc), detail=str(exc)
        ) from exc


def _authorise_channel(tenant_id: str, channel_id: str) -> None:
    """Fail closed when a channel belongs to a different tenant.

    ``channel_id`` is the form ``<tenant>::<channel>`` when the caller supplies
    one; the tenant component is verified in constant time.  A bare channel id
    is accepted and treated as belonging to the authenticated tenant, since the
    store already partitions by tenant.
    """
    if "::" not in channel_id:
        return
    claimed_tenant, _, _ = channel_id.partition("::")
    if not hmac.compare_digest(claimed_tenant.strip(), tenant_id):
        logger.warning(
            "policy_tenant_mismatch",
            extra={"token_tenant": tenant_id, "claimed_tenant": claimed_tenant},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Tenant mismatch: the channel targets a tenant the caller is not "
                "authorised to act on"
            ),
        )


def _store_channel(tenant_id: str, channel_id: str) -> str:
    """Normalise a channel id to its bare form for the tenant-partitioned store."""
    if "::" in channel_id:
        _, _, bare = channel_id.partition("::")
        return bare
    return channel_id


@router.post("/evaluate")
async def evaluate_policy(data: dict[str, Any], request: Request) -> dict[str, Any]:
    """Evaluate a decision against the authenticated tenant's policies."""
    tenant_id = _require_tenant(request, data.get("tenant_id"))

    decision_id = data["decision_id"]
    channel_id = data["channel_id"]
    _authorise_channel(tenant_id, channel_id)
    channel = _store_channel(tenant_id, channel_id)
    autonomy_level = AutonomyLevel(data.get("autonomy_level", "L1"))
    context = data.get("context", {})

    rules = store.get(tenant_id, channel)
    engine = PolicyEngine(rules)
    result = engine.evaluate(decision_id, channel, autonomy_level, context)

    return {
        "decision_id": result.decision_id,
        "channel_id": channel_id,
        "autonomy_level": result.autonomy_level.value,
        "overall_risk": result.overall_risk,
        "risk_scores": [
            {
                "category": rs.category.value,
                "score": rs.score,
                "threshold": rs.threshold,
            }
            for rs in result.risk_scores
        ],
        "approved": result.approved,
        "requires_human_override": result.requires_human_override,
        "policy_version": result.policy_version,
    }


@router.post("/policies")
async def create_policy(data: dict[str, Any], request: Request) -> dict[str, Any]:
    """Create a policy rule owned by the authenticated tenant."""
    tenant_id = _require_tenant(request, data.get("tenant_id"))

    channel_id = data["channel_id"]
    _authorise_channel(tenant_id, channel_id)
    channel = _store_channel(tenant_id, channel_id)

    rule = PolicyRule(
        rule_id=data["rule_id"],
        name=data.get("name", ""),
        condition=data.get("condition", {}),
        action=data.get("action", "BLOCK"),
        autonomy_level=AutonomyLevel(data["autonomy_level"])
        if data.get("autonomy_level")
        else None,
        tenant_ids=[tenant_id],
        channel_ids=[channel],
    )
    store.add(tenant_id, channel, rule)
    return {
        "rule_id": rule.rule_id,
        "channel_id": channel_id,
        "action": rule.action,
        "tenant_id": tenant_id,
    }


@router.get("/policies/{channel_id}")
async def list_policies(channel_id: str, request: Request) -> list[dict[str, Any]]:
    """List the authenticated tenant's policies for a channel."""
    tenant_id = _require_tenant(request)
    _authorise_channel(tenant_id, channel_id)
    channel = _store_channel(tenant_id, channel_id)

    return [
        {
            "rule_id": r.rule_id,
            "policy_type": r.condition.get("policy_type", "content"),
            "action": r.action,
            "autonomy_level": r.autonomy_level.value if r.autonomy_level else None,
        }
        for r in store.get(tenant_id, channel)
    ]
