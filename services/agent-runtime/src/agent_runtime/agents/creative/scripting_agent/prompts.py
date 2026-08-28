"""Prompt construction for Scripting Agent."""
from __future__ import annotations
from typing import Any
from prompt_registry.loader import PromptLoader

_loader = PromptLoader()


def build_draft_prompt(context: dict[str, Any]) -> str:
    """Render the script draft prompt."""
    return _loader.render(
        agent_id="scripting_agent",
        prompt_type="draft",
        version="v1",
        context=context,
    )


def build_critique_prompt(context: dict[str, Any]) -> str:
    """Render the script critique prompt."""
    return _loader.render(
        agent_id="scripting_agent",
        prompt_type="critique",
        version="v1",
        context=context,
    )


def build_rewrite_prompt(context: dict[str, Any]) -> str:
    """Render the script rewrite prompt."""
    return _loader.render(
        agent_id="scripting_agent",
        prompt_type="rewrite",
        version="v1",
        context=context,
    )
