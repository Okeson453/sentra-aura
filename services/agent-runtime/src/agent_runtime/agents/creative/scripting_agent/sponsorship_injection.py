"""Sponsorship injection for the Scripting Agent (Backend §46.2).

Injects a compliant sponsor mention into a structured script without
replacing the provider-generated creative content. Placement follows the
SponsorshipBrief.placement field.
"""
from __future__ import annotations

import logging
from typing import Any

from agent_runtime.agents.creative.scripting_agent.schemas import SponsorshipBrief
from agent_runtime.agents.creative.scripting_agent.state import ReflectionState, ScriptingState

logger = logging.getLogger(__name__)


def _disclosure_line(brief: SponsorshipBrief) -> str:
    if not brief.disclosure_required:
        return ""
    product = brief.product_name or brief.sponsor_name
    return f"This segment is sponsored by {brief.sponsor_name}" + (
        f" and their product {product}." if brief.product_name else "."
    )


def _mention_block(brief: SponsorshipBrief) -> str:
    points = brief.talking_points or []
    points_text = " ".join(points[:3]) if points else f"Check out {brief.sponsor_name}."
    disclosure = _disclosure_line(brief)
    parts = [p for p in (disclosure, points_text) if p]
    return " ".join(parts).strip()


def inject_sponsorship(
    script: dict[str, Any],
    brief: SponsorshipBrief | None,
    state: ReflectionState | None = None,
) -> dict[str, Any]:
    """Return a copy of script with sponsorship content injected.

    If brief is missing or has no sponsor_name, the script is returned unchanged.
    """
    if state is not None:
        state.advance(ScriptingState.SPONSORSHIP)

    if not brief or not brief.sponsor_name.strip():
        if state is not None:
            state.sponsorship_applied = False
        return script

    out = {
        "hook": script.get("hook", ""),
        "intro": script.get("intro", ""),
        "sections": list(script.get("sections") or []),
        "cta": script.get("cta", ""),
        "outro": script.get("outro", ""),
    }
    mention = _mention_block(brief)
    placement = (brief.placement or "mid-roll").lower()
    mentions_left = max(1, brief.max_mentions)

    if placement == "pre-roll" and mentions_left:
        out["hook"] = f"{mention} {out['hook']}".strip()
        mentions_left -= 1
    elif placement == "post-roll" and mentions_left:
        out["outro"] = f"{out['outro']} {mention}".strip()
        mentions_left -= 1
    elif placement == "natural" and mentions_left:
        # Append to intro as a soft transition
        out["intro"] = f"{out['intro']} {mention}".strip()
        mentions_left -= 1
    else:
        # mid-roll default: insert a dedicated section after first body section
        sponsor_section = {
            "title": f"Sponsor — {brief.sponsor_name}",
            "content": mention,
            "estimated_duration": 30,
            "b_roll_notes": f"Product shot / logo card for {brief.sponsor_name}",
        }
        sections = list(out["sections"])
        if sections:
            sections.insert(min(1, len(sections)), sponsor_section)
        else:
            sections.append(sponsor_section)
        out["sections"] = sections
        mentions_left -= 1

    if state is not None:
        state.sponsorship_applied = True
        state.rewritten_script = out
        # Keep draft if rewrite empty
        if state.draft_script is None:
            state.draft_script = out

    logger.info(
        "Sponsorship injected for sponsor=%s placement=%s",
        brief.sponsor_name,
        placement,
    )
    return out
