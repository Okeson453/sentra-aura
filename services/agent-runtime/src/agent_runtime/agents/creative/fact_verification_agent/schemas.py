"""Schemas for Fact Verification Agent (Architecture §4.2).

Inputs: draft script segments, ResearchBundle, claim graph.
Outputs: verified claims with confidence scores, contradiction alerts.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FactCheckRequest(BaseModel):
    """Accepts claims and/or a ResearchBundle from research_agent."""

    claims: list[str] = Field(default_factory=list)
    # ResearchBundle — same shape as research_agent.schemas.ResearchResponse
    research_bundle: dict[str, Any] | None = None
    # Legacy field name still accepted (string brief)
    research_brief: str = ""
    draft_segments: list[str] = Field(default_factory=list)
    min_confidence_threshold: float = 0.6
    cross_reference_sources: list[str] = Field(default_factory=list)
    task_type: str = "verify"


class VerificationResult(BaseModel):
    claim: str
    verdict: str  # verified | false | mixed | unverified | disputed
    confidence: float
    supporting_sources: list[str] = Field(default_factory=list)
    contradicting_sources: list[str] = Field(default_factory=list)
    explanation: str = ""
    requires_human_review: bool = False
    source_ids: list[str] = Field(default_factory=list)


class FactCheckResponse(BaseModel):
    verifications: list[VerificationResult] = Field(default_factory=list)
    overall_confidence: float = 0.0
    unverifiable_count: int = 0
    contradiction_alerts: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    raw_provider_text: str | None = None
    provider_usage: dict[str, Any] | None = None
