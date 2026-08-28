"""Schemas for Research Agent — ResearchBundle (Architecture §4.2)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ResearchSource(BaseModel):
    source_id: str
    url: str = ""
    title: str = ""
    content: str = ""
    credibility_score: float = 0.0
    source_type: str = "web"
    # Boundary audit fields
    boundary_threat_level: str | None = None
    boundary_allowed: bool = True


class ResearchClaim(BaseModel):
    claim_text: str
    confidence: float = 0.0
    source_ids: list[str] = Field(default_factory=list)
    verified: bool = False


class ResearchRequest(BaseModel):
    topic: str = ""
    depth: str = "standard"
    channel_name: str = ""
    max_sources: int = 10
    topic_domains: list[str] = Field(default_factory=list)
    initial_query: str = ""
    existing_sources: list[str] = Field(default_factory=list)
    task_type: str = "gather"


class ResearchResponse(BaseModel):
    """ResearchBundle: claims, sources, entities, citations (§4.2)."""

    executive_summary: str
    key_findings: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[ResearchSource] = Field(default_factory=list)
    claims: list[ResearchClaim] = Field(default_factory=list)
    entities: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    statistics: list[dict[str, Any]] = Field(default_factory=list)
    expert_opinions: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    research_gaps: list[str] = Field(default_factory=list)
    confidence_score: float = 0.0
    boundary_audits: list[dict[str, Any]] = Field(default_factory=list)
    research_job_id: str | None = None
    raw_provider_text: str | None = None
    provider_usage: dict[str, Any] | None = None
