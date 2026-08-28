"""Pydantic schemas for the Executive Orchestrator Agent."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StrategyRequest(BaseModel):
    """Input payload for executive strategy / coordination."""

    channel_name: str = ""
    portfolio_name: str = ""
    autonomy_level: str = "L2"
    budget_remaining: float = 0.0
    planning_horizon: str = "30 days"
    trend_signals: list[dict[str, Any]] = Field(default_factory=list)
    audience_insights: str = ""
    performance_history: str = ""
    max_videos_per_week: int = 3
    avg_video_length: str = "10 minutes"
    brand_safety_level: str = "standard"
    human_approval_gates: str = "L3+ decisions"
    # Optional structured inputs from peer intelligence agents (Arch. §4.2)
    portfolio_plan: dict[str, Any] | None = None
    market_intelligence: dict[str, Any] | None = None
    resource_pool: dict[str, Any] | None = None
    channel_history: list[dict[str, Any]] = Field(default_factory=list)
    task_type: str = "strategy"  # strategy | coordinate | evaluate_escalations
    # Real orchestrator / workflow telemetry (not only test-injected scalars)
    workflow_state: dict[str, Any] | None = None
    """e.g. {active_workflows: [{id, started_at, status, last_progress_at}]}"""
    resource_metrics: dict[str, Any] | None = None
    """e.g. {cpu_utilization: 0.85, memory_utilization: 0.7, window_window_hours: 1.0}"""
    budget_metrics: dict[str, Any] | None = None
    """e.g. {allocated_usd: 1000, spent_usd: 1150}"""
    failure_history: list[dict[str, Any]] = Field(default_factory=list)
    """e.g. [{agent_id, failed_at, error}] ordered newest-last"""



class AgentAssignment(BaseModel):
    """Assignment of work to a downstream agent or swarm."""

    agent_id: str
    swarm: str
    task: str
    priority: str = "normal"
    inputs_ref: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)


class WorkflowNode(BaseModel):
    """One node in the inter-swarm workflow DAG."""

    node_id: str
    agent_id: str
    description: str
    depends_on: list[str] = Field(default_factory=list)


class StrategyResponse(BaseModel):
    """Canonical output of the Executive Orchestrator."""

    strategy_summary: str
    content_pillars: list[str] = Field(default_factory=list)
    publishing_schedule: list[dict[str, Any]] = Field(default_factory=list)
    resource_allocation: dict[str, Any] = Field(default_factory=dict)
    risk_mitigation: list[str] = Field(default_factory=list)
    kpis: dict[str, Any] = Field(default_factory=dict)
    agent_assignments: list[dict[str, Any]] = Field(default_factory=list)
    workflow_dag: list[dict[str, Any]] = Field(default_factory=list)
    coordination_notes: list[str] = Field(default_factory=list)
    escalations: list[dict[str, Any]] = Field(default_factory=list)
    raw_provider_text: str | None = None
    provider_usage: dict[str, Any] | None = None
