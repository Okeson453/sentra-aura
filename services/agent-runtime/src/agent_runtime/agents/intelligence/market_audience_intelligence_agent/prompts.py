"""Prompt construction for Market & Audience Intelligence Agent."""
from __future__ import annotations
from typing import Any
from prompt_registry.loader import PromptLoader

_loader = PromptLoader()


def build_analyze_prompt(context: dict[str, Any]) -> str:
    """Render the market analysis prompt."""
    return _loader.render(
        agent_id="market_audience_intelligence_agent",
        prompt_type="analyze",
        version="v1",
        context=context,
    )
