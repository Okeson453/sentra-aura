"""Prompt construction for Portfolio Strategy Agent."""
from __future__ import annotations
from typing import Any
from prompt_registry.loader import PromptLoader

_loader = PromptLoader()


def build_plan_prompt(context: dict[str, Any]) -> str:
    """Render the portfolio plan prompt."""
    return _loader.render(
        agent_id="portfolio_strategy_agent",
        prompt_type="plan",
        version="v1",
        context=context,
    )
