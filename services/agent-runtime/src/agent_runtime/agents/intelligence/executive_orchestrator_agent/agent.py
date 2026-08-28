"""Executive Orchestrator Agent — inter-swarm coordination and strategy (Arch. §4.2)."""
from __future__ import annotations

import json
import logging
from typing import Any

from agent_runtime.agents.base import BaseAgent
from agent_runtime.envelope import AgentMessageEnvelope
from agent_runtime.sandbox.runner import SandboxLimits

from agent_runtime.agents.intelligence.executive_orchestrator_agent.config import (
    ExecutiveOrchestratorConfig,
)
from agent_runtime.agents.intelligence.executive_orchestrator_agent.escalation import evaluate_escalations
from agent_runtime.agents.intelligence.executive_orchestrator_agent.coordination import (
    merge_strategy_from_provider,
)
from agent_runtime.agents.intelligence.executive_orchestrator_agent.schemas import (
    StrategyRequest,
    StrategyResponse,
)
from agent_runtime.agents.intelligence.executive_orchestrator_agent.state import (
    OrchestratorPhase,
    OrchestratorState,
)
from agent_runtime.agents.intelligence.executive_orchestrator_agent import tools as orch_tools
from agent_runtime.agents.intelligence.executive_orchestrator_agent.tools import try_parse_json_object

logger = logging.getLogger(__name__)


class ExecutiveOrchestratorAgent(BaseAgent[StrategyResponse]):
    def __init__(self, config: ExecutiveOrchestratorConfig | None = None, **kwargs: Any) -> None:
        limits = kwargs.pop("sandbox_limits", None) or SandboxLimits(
            allow_network=True, max_cpu_time_seconds=60.0
        )
        super().__init__(
            agent_id="executive_orchestrator_agent",
            name="Executive Orchestrator",
            domain="intelligence",
            version="1.0.0",
            autonomy_level="L2",
            sandbox_limits=limits,
            **kwargs,
        )
        self.config = config or ExecutiveOrchestratorConfig()
        self.register_tool("plan_workflow", orch_tools.plan_workflow)
        self.register_tool("dispatch_task", orch_tools.dispatch_task)

    @property
    def capabilities(self) -> list[str]:
        return [
            "strategy",
            "planning",
            "orchestration",
            "portfolio_coordination",
            "inter_swarm_workflow",
            "plan_workflow",
            "dispatch_task",
        ]

    async def execute(self, envelope: AgentMessageEnvelope) -> dict[str, Any]:
        payload = envelope.message.payload or {}
        if "task_type" not in payload and getattr(envelope.message, "task_type", None):
            payload = {**payload, "task_type": envelope.message.task_type}

        request = StrategyRequest(**payload)
        state = OrchestratorState()
        state.advance(OrchestratorPhase.INGESTING)

        request.channel_name = self.sanitize_input(request.channel_name, source="channel_name")
        request.audience_insights = self.sanitize_input(
            request.audience_insights, source="audience_insights"
        )
        request.performance_history = self.sanitize_input(
            request.performance_history, source="performance_history"
        )

        context = {
            "channel_name": request.channel_name,
            "portfolio_name": request.portfolio_name,
            "autonomy_level": request.autonomy_level,
            "budget_remaining": request.budget_remaining,
            "planning_horizon": request.planning_horizon or self.config.default_planning_horizon,
            "trend_signals": request.trend_signals,
            "audience_insights": request.audience_insights,
            "performance_history": request.performance_history,
            "max_videos_per_week": request.max_videos_per_week
            or self.config.default_max_videos_per_week,
            "avg_video_length": request.avg_video_length,
            "brand_safety_level": request.brand_safety_level,
            "human_approval_gates": request.human_approval_gates,
        }
        if request.portfolio_plan:
            context["portfolio_plan"] = json.dumps(request.portfolio_plan)
        if request.market_intelligence:
            context["market_intelligence"] = json.dumps(request.market_intelligence)
        if request.resource_pool:
            context["resource_pool"] = json.dumps(request.resource_pool)

        state.advance(OrchestratorPhase.PLANNING)
        plan = await self.invoke_tool(
            "plan_workflow", (), {"context": context, "config": self.config}
        )
        state.record_provider(str(plan.get("content") or ""), plan.get("usage"))

        parsed = try_parse_json_object(str(plan.get("content") or ""))
        strategy = merge_strategy_from_provider(parsed, request, str(plan.get("content") or ""))

        state.advance(OrchestratorPhase.COORDINATING)
        # request.model_dump for dispatch (pydantic v2)
        req_payload = request.model_dump() if hasattr(request, "model_dump") else request.dict()
        dispatched = await self.invoke_tool(
            "dispatch_task",
            (),
            {"request_payload": req_payload, "strategy": strategy},
        )

        escalations = evaluate_escalations(
            workflow_state=request.workflow_state,
            resource_metrics=request.resource_metrics,
            budget_metrics=request.budget_metrics,
            failure_history=request.failure_history,
        )
        notes = list(dispatched["coordination_notes"] or [])
        if escalations:
            notes.append(f"ESCALATIONS_TRIGGERED:{len(escalations)}")
            for e in escalations:
                notes.append(f"ESC:{e['condition']}:{e.get('message','')}")

        response = StrategyResponse(
            strategy_summary=strategy["strategy_summary"],
            content_pillars=strategy["content_pillars"],
            publishing_schedule=strategy["publishing_schedule"],
            resource_allocation=strategy["resource_allocation"],
            risk_mitigation=strategy["risk_mitigation"] + [
                e.get("message", e["condition"]) for e in escalations
            ],
            kpis=strategy["kpis"],
            agent_assignments=dispatched["agent_assignments"],
            workflow_dag=dispatched["workflow_dag"],
            coordination_notes=notes,
            escalations=escalations,
            raw_provider_text=str(plan.get("content") or ""),
            provider_usage=state.provider_usages[-1] if state.provider_usages else None,
        )
        state.advance(OrchestratorPhase.COMPLETED)
        return response.model_dump()
