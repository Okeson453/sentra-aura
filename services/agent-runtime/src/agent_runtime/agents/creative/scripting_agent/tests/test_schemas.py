"""Schema tests for Scripting Agent."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent_runtime.agents.creative.scripting_agent.schemas import (
    ScriptRequest,
    ScriptResponse,
    ScriptSection,
    SponsorshipBrief,
)


def test_script_request_defaults():
    req = ScriptRequest(video_title="Hello")
    assert req.task_type == "draft"
    assert req.target_length == "10 minutes"
    assert req.sponsorship is None


def test_script_request_with_sponsorship():
    req = ScriptRequest(
        video_title="T",
        sponsorship=SponsorshipBrief(sponsor_name="Acme", placement="pre-roll"),
    )
    assert req.sponsorship.sponsor_name == "Acme"
    assert req.sponsorship.placement == "pre-roll"


def test_script_section_model():
    s = ScriptSection(title="Hook", content="Hi", estimated_duration=30, b_roll_notes="x")
    assert s.title == "Hook"


def test_script_response_roundtrip():
    resp = ScriptResponse(
        script={"hook": "a", "intro": "b", "sections": [], "cta": "c", "outro": "d"},
        word_count=4,
        estimated_duration=10,
        retention_hooks=[{"timestamp": "0:00", "tactic": "hook"}],
        seo_notes=["kw"],
        suggested_b_roll=["broll"],
        sponsorship_applied=False,
        reflection_rounds=1,
        raw_provider_text="provider said this",
    )
    data = resp.model_dump()
    assert data["raw_provider_text"] == "provider said this"
    assert ScriptResponse(**data).word_count == 4


def test_invalid_response_missing_script():
    with pytest.raises(ValidationError):
        ScriptResponse()  # script is required
