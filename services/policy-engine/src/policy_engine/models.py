"""Models for the Policy Engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class AutonomyLevel(str, Enum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"


class RiskCategory(str, Enum):
    CONTENT = "content"
    COPYRIGHT = "copyright"
    PLATFORM = "platform"
    BRAND = "brand"
    FINANCIAL = "financial"
    LEGAL = "legal"
    ETHICAL = "ethical"


class RuleType(str, Enum):
    EXACT = "exact"
    REGEX = "regex"
    RANGE = "range"
    SEMANTIC = "semantic"
    COMPOSITE = "composite"
    TEMPORAL = "temporal"


class CompositeOperator(str, Enum):
    AND = "AND"
    OR = "OR"
    NOT = "NOT"


@dataclass
class RiskScore:
    category: RiskCategory
    score: float
    threshold: float
    factors: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class PolicyRule:
    rule_id: str
    name: str
    rule_type: RuleType = RuleType.EXACT
    condition: dict[str, Any] = field(default_factory=dict)
    action: str = "BLOCK"  # BLOCK, REQUIRE_APPROVAL, WARN, ESCALATE
    autonomy_level: AutonomyLevel | None = None
    channel_ids: list[str] | None = None
    tenant_ids: list[str] | None = None
    enabled: bool = True
    composite_operator: CompositeOperator | None = None
    sub_conditions: list[dict[str, Any]] | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PolicyEvaluation:
    decision_id: str
    channel_id: str
    autonomy_level: AutonomyLevel
    overall_risk: float
    risk_scores: list[RiskScore]
    approved: bool
    requires_human_override: bool
    policy_version: int
    triggered_rules: list[str] = field(default_factory=list)
    evaluated_at: datetime = field(default_factory=datetime.utcnow)
