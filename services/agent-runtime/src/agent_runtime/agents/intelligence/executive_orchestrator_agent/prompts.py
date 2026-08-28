"""Prompt construction for Executive Orchestrator Agent."""
from __future__ import annotations
from typing import Any
from prompt_registry.loader import PromptLoader

_loader = PromptLoader()


def build_strategy_prompt(context: dict[str, Any]) -> str:
    """Render the strategy prompt with context variables."""
    return _loader.render(
        agent_id="executive_orchestrator_agent",
        prompt_type="strategy",
        version="v1",
        context=context,
    )
