"""Draft → Critique → Rewrite reflection loop for the Scripting Agent.

Every LLM step goes through BaseAgent.invoke_tool → permissions.enforce →
registered matrix tools (draft_script / critique_script / rewrite_section).
"""
from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from agent_runtime.agents.creative.scripting_agent.config import ScriptingAgentConfig
from agent_runtime.agents.creative.scripting_agent.schemas import CritiqueResult, ScriptRequest
from agent_runtime.agents.creative.scripting_agent.state import ReflectionState, ScriptingState

logger = logging.getLogger(__name__)

# invoke_tool(tool_name, args=(), kwargs=None) -> Any
ToolInvoker = Callable[..., Awaitable[Any]]


def _context_from_request(request: ScriptRequest, **extra: Any) -> dict[str, Any]:
    brief = request.research_brief
    if isinstance(brief, dict):
        brief_str = json.dumps(brief) if brief else ""
    else:
        brief_str = str(brief or "")

    ctx: dict[str, Any] = {
        "channel_name": request.channel_name,
        "video_title": request.video_title,
        "target_length": request.target_length,
        "tone": request.tone,
        "research_brief": brief_str,
        "target_keywords": request.target_keywords,
        "audience_profile": request.audience_profile,
        "brand_guidelines": request.brand_guidelines,
        "target_audience": request.audience_profile or "general",
    }
    ctx.update(extra)
    return ctx


def _usage_from_result(result: dict[str, Any]) -> dict[str, Any]:
    return dict(result.get("usage") or {})


async def run_draft(
    request: ScriptRequest,
    state: ReflectionState,
    config: ScriptingAgentConfig,
    invoker: ToolInvoker,
) -> dict[str, Any]:
    state.advance(ScriptingState.DRAFTING)
    context = _context_from_request(request)
    result = await invoker("draft_script", (), {"context": context, "config": config})
    if not isinstance(result, dict):
        raise RuntimeError(f"draft_script returned non-dict: {type(result)}")
    text = str(result.get("content") or "")
    state.record_provider(text, _usage_from_result(result))
    script = result.get("script") or {}
    state.draft_script = script
    return script


async def run_critique(
    request: ScriptRequest,
    script: dict[str, Any],
    state: ReflectionState,
    config: ScriptingAgentConfig,
    invoker: ToolInvoker,
) -> CritiqueResult:
    state.advance(ScriptingState.CRITIQUING)
    context = _context_from_request(
        request,
        script_to_critique=json.dumps(script)[:4000],
        script=json.dumps(script)[:4000],
    )
    result = await invoker("critique_script", (), {"context": context, "config": config})
    if not isinstance(result, dict):
        raise RuntimeError(f"critique_script returned non-dict: {type(result)}")
    text = str(result.get("content") or "")
    state.record_provider(text, _usage_from_result(result))
    from agent_runtime.agents.creative.scripting_agent.tools import try_parse_json_object

    parsed = try_parse_json_object(text) or {}
    critique = CritiqueResult(
        overall_score=float(parsed.get("overall_score") or 0.5),
        strengths=list(parsed.get("strengths") or []),
        weaknesses=list(parsed.get("weaknesses") or []),
        action_items=list(parsed.get("action_items") or ["Revise for clarity"]),
        approval_status=str(parsed.get("approval_status") or "approved_with_revisions"),
        raw_text=text,
    )
    state.critique = critique.model_dump()
    return critique


async def run_rewrite(
    request: ScriptRequest,
    script: dict[str, Any],
    critique: CritiqueResult,
    state: ReflectionState,
    config: ScriptingAgentConfig,
    invoker: ToolInvoker,
) -> dict[str, Any]:
    state.advance(ScriptingState.REWRITING)
    context = _context_from_request(
        request,
        original_script=json.dumps(script)[:4000],
        critique_feedback=json.dumps(critique.model_dump())[:2000],
        script=json.dumps(script)[:4000],
    )
    result = await invoker("rewrite_section", (), {"context": context, "config": config})
    if not isinstance(result, dict):
        raise RuntimeError(f"rewrite_section returned non-dict: {type(result)}")
    text = str(result.get("content") or "")
    state.record_provider(text, _usage_from_result(result))
    rewritten = result.get("script") or script
    state.rewritten_script = rewritten
    return rewritten


async def run_reflection_loop(
    request: ScriptRequest,
    *,
    config: ScriptingAgentConfig | None = None,
    invoker: ToolInvoker,
    max_rounds: int | None = None,
) -> ReflectionState:
    cfg = config or ScriptingAgentConfig()
    max_rounds = max_rounds if max_rounds is not None else 1
    state = ReflectionState(max_rounds=max_rounds)
    task = (request.task_type or "draft").lower()

    try:
        if task == "critique":
            if not request.existing_script:
                raise ValueError("critique task_type requires existing_script")
            state.draft_script = request.existing_script
            await run_critique(request, state.draft_script, state, cfg, invoker)
            state.advance(ScriptingState.COMPLETED)
            return state

        if task == "rewrite":
            if not request.existing_script:
                raise ValueError("rewrite task_type requires existing_script")
            state.draft_script = request.existing_script
            critique = CritiqueResult(
                raw_text=str(request.critique_feedback or ""),
                action_items=[str(request.critique_feedback or "general improvement")],
                approval_status="approved_with_revisions",
            )
            if isinstance(request.critique_feedback, dict):
                critique = CritiqueResult(**{**critique.model_dump(), **request.critique_feedback})
            state.critique = critique.model_dump()
            await run_rewrite(request, state.draft_script, critique, state, cfg, invoker)
            state.advance(ScriptingState.COMPLETED)
            return state

        script = await run_draft(request, state, cfg, invoker)

        if task == "draft" and max_rounds <= 0:
            state.advance(ScriptingState.COMPLETED)
            return state

        for round_idx in range(max(1, max_rounds)):
            state.round = round_idx + 1
            critique = await run_critique(request, script, state, cfg, invoker)
            if critique.approval_status == "approved":
                logger.info("Script approved on round %d", state.round)
                break
            script = await run_rewrite(request, script, critique, state, cfg, invoker)

        state.advance(ScriptingState.COMPLETED)
        return state

    except Exception as exc:
        logger.exception("Reflection loop failed: %s", exc)
        state.record_error(str(exc))
        state.advance(ScriptingState.FAILED)
        raise


def finalize_script_payload(state: ReflectionState, request: ScriptRequest) -> dict[str, Any]:
    """Pick the best script from reflection state and attach metrics."""
    from agent_runtime.agents.creative.scripting_agent.tools import word_count_of_script

    script = state.rewritten_script or state.draft_script or {}
    wc = word_count_of_script(script)
    duration = max(30, int(wc / 2.5))  # ~150 wpm
    retention = []
    if script.get("hook"):
        retention.append({"timestamp": "0:00", "tactic": "Hook from provider draft"})
    for i, section in enumerate(script.get("sections") or []):
        title = section.get("title", f"section-{i}") if isinstance(section, dict) else f"section-{i}"
        retention.append({"timestamp": f"{(i + 1) * 2}:00", "tactic": f"Section beat: {title}"})

    seo: list[str] = []
    if request.target_keywords:
        seo.append(f"Primary keyword '{request.target_keywords[0]}' targeted in title/script")
    b_roll = []
    for section in script.get("sections") or []:
        if isinstance(section, dict) and section.get("b_roll_notes"):
            b_roll.append(section["b_roll_notes"])

    return {
        "script": script,
        "word_count": wc,
        "estimated_duration": duration,
        "retention_hooks": retention,
        "seo_notes": seo,
        "suggested_b_roll": b_roll or ["Provider-derived visuals"],
        "critique": state.critique,
        "rewrite_notes": {"rounds": state.round, "had_rewrite": state.rewritten_script is not None},
        "sponsorship_applied": state.sponsorship_applied,
        "reflection_rounds": state.round,
        "raw_provider_text": state.provider_texts[-1] if state.provider_texts else None,
        "provider_usage": state.provider_usages[-1] if state.provider_usages else None,
    }
