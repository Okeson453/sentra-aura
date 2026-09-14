"""Authoritative Temporal worker registration for the orchestrator."""
from __future__ import annotations

from orchestrator.activities import (
    draft_script,
    execute_agent_task,
    generate_clips,
    generate_visuals,
    optimize_policy,
    produce_voice,
    publish_content,
    record_analytics,
    render_video,
    research_topic,
    update_learning,
)
from orchestrator.workflows import AgentWorkflow, LongFormVideoWorkflow

ALL_ACTIVITIES = (
    execute_agent_task,
    research_topic,
    draft_script,
    produce_voice,
    generate_visuals,
    render_video,
    generate_clips,
    publish_content,
    record_analytics,
    update_learning,
    optimize_policy,
)

ALL_WORKFLOWS = (AgentWorkflow, LongFormVideoWorkflow)

__all__ = ["ALL_ACTIVITIES", "ALL_WORKFLOWS"]
