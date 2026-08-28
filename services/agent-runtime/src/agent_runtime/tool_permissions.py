"""Tool permission system enforcing least-privilege access for agent tool calls.

Every tool invocation from an agent is checked against a permission matrix
that maps (agent_id, tool_name, action) -> allowed/denied with justification.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class PermissionDecision(Enum):
    ALLOW = "allow"
    DENY = "deny"
    ESCALATE = "escalate"


@dataclass(frozen=True)
class ToolPermission:
    """A single tool permission rule."""

    agent_id: str
    tool_name: str
    action: str
    decision: PermissionDecision
    justification: str = ""
    risk_tier: str = "medium"
    requires_approval: bool = False


class PermissionMatrix:
    """In-memory permission matrix with default-deny semantics."""

    # Default permissions for each agent domain
    DEFAULT_PERMISSIONS: list[ToolPermission] = [
        # Intelligence domain
        ToolPermission("executive_orchestrator_agent", "plan_workflow", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("executive_orchestrator_agent", "dispatch_task", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("portfolio_strategy_agent", "analyze_portfolio", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("market_audience_intelligence_agent", "fetch_trends", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("market_audience_intelligence_agent", "analyze_sentiment", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("research_agent", "search_web", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("research_agent", "fetch_source", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("research_agent", "synthesize_brief", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("fact_verification_agent", "verify_claim", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("fact_verification_agent", "cross_reference", "execute", PermissionDecision.ALLOW, "Core capability"),
        # Creative domain
        ToolPermission("content_strategist_ideation_agent", "generate_concepts", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("content_strategist_ideation_agent", "score_ideas", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("scripting_agent", "draft_script", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("scripting_agent", "critique_script", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("scripting_agent", "rewrite_section", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("voice_agent", "synthesize_speech", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("voice_agent", "plan_delivery", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("voice_agent", "clone_voice", "execute", PermissionDecision.ESCALATE, "Requires legal review", requires_approval=True),
        ToolPermission("visual_asset_agent", "generate_image", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("visual_asset_agent", "edit_image", "execute", PermissionDecision.ALLOW, "Core capability"),
        # Production domain
        ToolPermission("scene_shot_agent", "plan_shots", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("video_production_agent", "assemble_timeline", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("video_production_agent", "render_video", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("localization_agent", "translate", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("localization_agent", "dub_audio", "execute", PermissionDecision.ALLOW, "Core capability"),
        # Clipping domain
        ToolPermission("ai_clipping_agent", "select_clips", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("reframing_agent", "reframe_clip", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("captioning_agent", "generate_captions", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("repurposing_agent", "build_derivatives", "execute", PermissionDecision.ALLOW, "Core capability"),
        # Distribution domain
        ToolPermission("thumbnail_agent", "generate_thumbnail", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("seo_packaging_agent", "package_seo", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("scheduling_agent", "schedule_publish", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("publishing_agent", "publish_content", "execute", PermissionDecision.ESCALATE, "Public-facing publish", requires_approval=True),
        ToolPermission("community_engagement_agent", "engage_comments", "execute", PermissionDecision.ESCALATE, "Public-facing replies", requires_approval=True),
        # Operations domain
        ToolPermission("rights_remediation_agent", "remediate_rights", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("crisis_sentiment_anomaly_agent", "detect_anomaly", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("analytics_agent", "analyze_metrics", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("experimentation_agent", "run_experiment", "execute", PermissionDecision.ESCALATE, "May mutate live traffic", requires_approval=True),
        ToolPermission("optimization_agent", "optimize", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("quality_control_agent", "qc_check", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("compliance_agent", "check_compliance", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("cost_control_agent", "track_cost", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("memory_agent", "store_memory", "execute", PermissionDecision.ALLOW, "Core capability"),
        ToolPermission("memory_agent", "recall_memory", "execute", PermissionDecision.ALLOW, "Core capability"),
        # Dangerous operations — default deny
        ToolPermission("*", "delete_asset", "execute", PermissionDecision.ESCALATE, "Destructive operation", requires_approval=True),
        ToolPermission("*", "publish_content", "execute", PermissionDecision.ESCALATE, "Public-facing operation", requires_approval=True),
        ToolPermission("*", "modify_policy", "execute", PermissionDecision.DENY, "Policy changes require human"),
        ToolPermission("*", "access_pii", "execute", PermissionDecision.ESCALATE, "Sensitive data access", requires_approval=True),
    ]

    def __init__(self, custom_permissions: list[ToolPermission] | None = None) -> None:
        self._rules: dict[str, ToolPermission] = {}
        for perm in self.DEFAULT_PERMISSIONS:
            self._add_rule(perm)
        if custom_permissions:
            for perm in custom_permissions:
                self._add_rule(perm)

    def _rule_key(self, agent_id: str, tool_name: str, action: str) -> str:
        return f"{agent_id}:{tool_name}:{action}"

    def _add_rule(self, perm: ToolPermission) -> None:
        key = self._rule_key(perm.agent_id, perm.tool_name, perm.action)
        self._rules[key] = perm

    def check(
        self,
        agent_id: str,
        tool_name: str,
        action: str = "execute",
    ) -> ToolPermission:
        """Check permission for a tool invocation. Default-deny if no rule exists."""
        # Exact match
        key = self._rule_key(agent_id, tool_name, action)
        if key in self._rules:
            return self._rules[key]

        # Wildcard match
        wildcard_key = self._rule_key("*", tool_name, action)
        if wildcard_key in self._rules:
            return self._rules[wildcard_key]

        # Default deny
        return ToolPermission(
            agent_id=agent_id,
            tool_name=tool_name,
            action=action,
            decision=PermissionDecision.DENY,
            justification="No permission rule defined — default deny",
            risk_tier="unknown",
        )

    def grant(
        self,
        agent_id: str,
        tool_name: str,
        action: str,
        justification: str = "",
        requires_approval: bool = False,
    ) -> None:
        """Grant a permission."""
        perm = ToolPermission(
            agent_id=agent_id,
            tool_name=tool_name,
            action=action,
            decision=PermissionDecision.ALLOW,
            justification=justification,
            requires_approval=requires_approval,
        )
        self._add_rule(perm)
        logger.info("Granted %s to %s for %s", action, agent_id, tool_name)

    def revoke(self, agent_id: str, tool_name: str, action: str) -> None:
        """Revoke a permission by replacing with explicit deny."""
        perm = ToolPermission(
            agent_id=agent_id,
            tool_name=tool_name,
            action=action,
            decision=PermissionDecision.DENY,
            justification="Explicitly revoked",
        )
        self._add_rule(perm)
        logger.info("Revoked %s from %s for %s", action, agent_id, tool_name)

    def list_permissions(self, agent_id: str | None = None) -> list[ToolPermission]:
        """List all permissions, optionally filtered by agent."""
        perms = list(self._rules.values())
        if agent_id:
            perms = [p for p in perms if p.agent_id == agent_id or p.agent_id == "*"]
        return perms


class ToolPermissionEnforcer:
    """Enforces tool permissions at the point of invocation."""

    def __init__(self, matrix: PermissionMatrix) -> None:
        self.matrix = matrix
        self._audit_log: list[dict[str, Any]] = []

    async def enforce(
        self,
        agent_id: str,
        tool_name: str,
        action: str = "execute",
        context: dict[str, Any] | None = None,
    ) -> ToolPermission:
        """Enforce permission and log the decision."""
        perm = self.matrix.check(agent_id, tool_name, action)

        entry = {
            "agent_id": agent_id,
            "tool_name": tool_name,
            "action": action,
            "decision": perm.decision.value,
            "justification": perm.justification,
            "requires_approval": perm.requires_approval,
            "context": context or {},
        }
        self._audit_log.append(entry)

        if perm.decision == PermissionDecision.DENY:
            logger.warning("Permission DENIED: %s -> %s:%s", agent_id, tool_name, action)
            raise PermissionDeniedError(agent_id, tool_name, action, perm.justification)

        if perm.decision == PermissionDecision.ESCALATE:
            logger.warning("Permission ESCALATED: %s -> %s:%s", agent_id, tool_name, action)
            if perm.requires_approval:
                raise ApprovalRequiredError(agent_id, tool_name, action, perm.justification)

        logger.info("Permission ALLOWED: %s -> %s:%s", agent_id, tool_name, action)
        return perm

    def get_audit_log(self) -> list[dict[str, Any]]:
        return list(self._audit_log)


class PermissionDeniedError(Exception):
    def __init__(self, agent_id: str, tool_name: str, action: str, reason: str) -> None:
        super().__init__(f"Permission denied: {agent_id} cannot {action} {tool_name} — {reason}")
        self.agent_id = agent_id
        self.tool_name = tool_name
        self.action = action
        self.reason = reason


class ApprovalRequiredError(Exception):
    def __init__(
        self,
        agent_id: str,
        tool_name: str,
        action: str,
        reason: str,
        approval_id: str | None = None,
        scope_key: str = "",
    ) -> None:
        msg = f"Approval required: {agent_id} -> {action} {tool_name} — {reason}"
        if approval_id:
            msg += f" [approval_id={approval_id}]"
        super().__init__(msg)
        self.agent_id = agent_id
        self.tool_name = tool_name
        self.action = action
        self.reason = reason
        self.approval_id = approval_id
        self.scope_key = scope_key
