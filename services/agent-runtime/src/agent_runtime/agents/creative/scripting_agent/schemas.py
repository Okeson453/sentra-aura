"""Pydantic schemas for the Scripting Agent."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ScriptSection(BaseModel):
    """One body section of a video script."""

    title: str
    content: str
    estimated_duration: int = 60
    b_roll_notes: str = ""


class SponsorshipBrief(BaseModel):
    """Optional sponsorship payload for injection into the script."""

    sponsor_name: str = ""
    product_name: str = ""
    talking_points: list[str] = Field(default_factory=list)
    placement: str = "mid-roll"  # pre-roll | mid-roll | post-roll | natural
    disclosure_required: bool = True
    max_mentions: int = 1


class ScriptRequest(BaseModel):
    """Input payload for the Scripting Agent."""

    video_title: str = ""
    channel_name: str = ""
    target_length: str = "10 minutes"
    tone: str = "conversational and informative"
    research_brief: dict[str, Any] | str = Field(default_factory=dict)
    target_keywords: list[str] = Field(default_factory=list)
    audience_profile: str = ""
    brand_guidelines: str = ""
    task_type: str = "draft"  # draft | critique | rewrite | full_loop
    existing_script: dict[str, Any] | None = None
    critique_feedback: dict[str, Any] | str | None = None
    sponsorship: SponsorshipBrief | None = None
    max_reflection_rounds: int = 1


class ScriptBody(BaseModel):
    """Structured script body."""

    hook: str = ""
    intro: str = ""
    sections: list[ScriptSection] = Field(default_factory=list)
    cta: str = ""
    outro: str = ""


class RetentionHook(BaseModel):
    timestamp: str
    tactic: str


class ScriptResponse(BaseModel):
    """Canonical output of the Scripting Agent."""

    script: dict[str, Any]
    word_count: int = 0
    estimated_duration: int = 0
    retention_hooks: list[dict[str, Any]] = Field(default_factory=list)
    seo_notes: list[str] = Field(default_factory=list)
    suggested_b_roll: list[str] = Field(default_factory=list)
    critique: dict[str, Any] | None = None
    rewrite_notes: dict[str, Any] | None = None
    sponsorship_applied: bool = False
    reflection_rounds: int = 0
    raw_provider_text: str | None = None
    provider_usage: dict[str, Any] | None = None


class CritiqueResult(BaseModel):
    """Structured critique of a draft script."""

    overall_score: float = 0.0
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    suggested_rewrites: list[str] = Field(default_factory=list)
    approval_status: str = "approved_with_revisions"  # approved | approved_with_revisions | rejected
    raw_text: str = ""
