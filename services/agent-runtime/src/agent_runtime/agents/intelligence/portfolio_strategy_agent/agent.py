"""Portfolio Strategy Agent — channel goals, content mix, budget allocation (§4.2)."""
from __future__ import annotations

import json
import logging
from typing import Any

from agent_runtime.agents.base import BaseAgent
from agent_runtime.sandbox.runner import SandboxLimits
from agent_runtime.envelope import AgentMessageEnvelope

from agent_runtime.agents.intelligence.portfolio_strategy_agent.config import (
    PortfolioStrategyConfig,
)
from agent_runtime.agents.intelligence.portfolio_strategy_agent.schemas import (
    ChannelAllocation,
    PortfolioPlanRequest,
    PortfolioPlanResponse,
)
from agent_runtime.agents.intelligence.portfolio_strategy_agent.state import PSAPhase, PSAState
from agent_runtime.agents.intelligence.portfolio_strategy_agent import tools as ps_tools
from agent_runtime.agents.intelligence.portfolio_strategy_agent.tools import (
    analyze_portfolio,
    render_plan_prompt,
    try_parse_json_object,
)

logger = logging.getLogger(__name__)


class PortfolioStrategyAgent(BaseAgent[PortfolioPlanResponse]):
    """Owns channel-level goals, content mix, and budget allocation."""

    def __init__(self, config: PortfolioStrategyConfig | None = None, **kwargs: Any) -> None:
        limits = kwargs.pop("sandbox_limits", None) or SandboxLimits(allow_network=True, max_cpu_time_seconds=60.0)
        super().__init__(
            agent_id="portfolio_strategy_agent",
            name="Portfolio Strategy",
            domain="intelligence",
            version="1.0.0",
            autonomy_level="L2",
            sandbox_limits=limits,
            **kwargs,
        )
        self.config = config or PortfolioStrategyConfig()
        self.register_tool("analyze_portfolio", ps_tools.analyze_portfolio)

    @property
    def capabilities(self) -> list[str]:
        return [
            "portfolio_planning",
            "budget_allocation",
            "content_calendar",
            "risk_assessment",
            "analyze_portfolio",
            "topic_quotas",
        ]

    async def execute(self, envelope: AgentMessageEnvelope) -> dict[str, Any]:
        payload = envelope.message.payload or {}
        if "task_type" not in payload and getattr(envelope.message, "task_type", None):
            payload = {**payload, "task_type": envelope.message.task_type}

        request = PortfolioPlanRequest(**payload)
        state = PSAState()
        state.advance(PSAPhase.ANALYZING)

        request.portfolio_name = self.sanitize_input(
            request.portfolio_name, source="portfolio_name"
        )

        channels = request.channels or []
        context = {
            "portfolio_name": request.portfolio_name,
            "channel_count": len(channels) or 1,
            "total_budget": request.total_budget_usd,
            "total_budget_usd": request.total_budget_usd,
            "reporting_period": f"{request.planning_period_days} days",
            "planning_period_days": request.planning_period_days,
            "channels": channels,
            "content_themes": request.content_themes,
            "risk_tolerance": request.risk_tolerance,
            "max_budget_share": int(self.config.max_budget_share * 100),
            "channel_performance": (
                json.dumps(request.historical_performance)
                if isinstance(request.historical_performance, dict)
                else (request.historical_performance or "")
            ),
            "budget_utilization": json.dumps(
                {"total_budget_usd": request.total_budget_usd, "channels": channels}
            ),
            "cross_channel_trends": json.dumps(request.market_intelligence or {}),
            "channel_goals": json.dumps(request.channel_goals or []),
        }

        prompt = render_plan_prompt(context)
        llm = await self.invoke_tool("analyze_portfolio", (), {"prompt": prompt, "config": self.config})
        state.provider_texts.append(llm.content)
        usage = {
            "prompt_tokens": llm.prompt_tokens,
            "completion_tokens": llm.completion_tokens,
            "total_tokens": llm.total_tokens,
            "estimated_cost_usd": llm.cost_usd,
        }
        state.provider_usages.append(usage)

        parsed = try_parse_json_object(llm.content) or {}
        response = self._build_response(request, parsed, llm.content, usage)
        state.advance(PSAPhase.COMPLETED)
        logger.info(
            "PortfolioStrategy plan for %s budget=%.2f",
            request.portfolio_name,
            request.total_budget_usd,
        )
        return response.model_dump()

    def _build_response(
        self,
        request: PortfolioPlanRequest,
        parsed: dict[str, Any],
        raw_text: str,
        usage: dict[str, Any],
    ) -> PortfolioPlanResponse:
        channels = request.channels or [{"channel_id": "default"}]
        n = max(1, len(channels))
        default_share = round(request.total_budget_usd / n, 2)

        allocations: list[ChannelAllocation] = []
        raw_allocs = parsed.get("channel_allocations") or []
        if raw_allocs:
            for i, item in enumerate(raw_allocs):
                if not isinstance(item, dict):
                    continue
                allocations.append(
                    ChannelAllocation(
                        channel_id=str(
                            item.get("channel_id")
                            or channels[i].get("channel_id", f"ch_{i}")
                            if i < len(channels)
                            else f"ch_{i}"
                        ),
                        budget_usd=float(item.get("budget_usd") or default_share),
                        video_count=int(item.get("video_count") or 2),
                        priority=int(item.get("priority") or i + 1),
                        topic_quota=dict(item.get("topic_quota") or {}),
                    )
                )
        if not allocations:
            themes = request.content_themes or ["general"]
            for i, ch in enumerate(channels):
                cid = str(ch.get("channel_id", f"ch_{i}"))
                allocations.append(
                    ChannelAllocation(
                        channel_id=cid,
                        budget_usd=default_share,
                        video_count=max(2, int(default_share / 100) if default_share else 2),
                        priority=i + 1,
                        topic_quota={themes[0]: 2} if themes else {},
                    )
                )

        topic_quotas: dict[str, int] = dict(parsed.get("topic_quotas") or {})
        if not topic_quotas:
            for theme in request.content_themes or ["general"]:
                topic_quotas[str(theme)] = max(1, int((request.max_videos_per_week or 3)))
            for a in allocations:
                for k, v in a.topic_quota.items():
                    topic_quotas[k] = topic_quotas.get(k, 0) + int(v)

        budget_allocation: dict[str, float] = dict(parsed.get("budget_allocation") or {})
        if not budget_allocation:
            for a in allocations:
                budget_allocation[a.channel_id] = a.budget_usd
            # stage split used by executive_orchestrator coordination
            budget_allocation.setdefault("production", 0.35)
            budget_allocation.setdefault("research", 0.2)
            budget_allocation.setdefault("distribution", 0.15)

        themes = list(parsed.get("cross_channel_themes") or request.content_themes or [])
        if not themes:
            themes = [request.portfolio_name, "core"]

        summary = str(
            parsed.get("portfolio_plan_summary")
            or (
                f"Plan for {request.portfolio_name} over {request.planning_period_days} days, "
                f"budget ${request.total_budget_usd:.2f}. {raw_text[:240]}"
            )
        )

        # High cadence or high channel count → emphasize distribution for orchestrator
        total_videos = sum(a.video_count for a in allocations)
        emphasize = bool(
            parsed.get("emphasize_distribution")
            or (request.max_videos_per_week or 0) >= 5
            or total_videos >= 12
        )

        portfolio_plan = {
            "summary": summary,
            "topic_quotas": topic_quotas,
            "budget_allocation": budget_allocation,
            "channel_allocations": [a.model_dump() for a in allocations],
            "emphasize_distribution": emphasize,
            "cross_channel_themes": themes,
            "planning_period_days": request.planning_period_days,
            "portfolio_name": request.portfolio_name,
        }

        return PortfolioPlanResponse(
            portfolio_plan_summary=summary,
            channel_allocations=allocations,
            topic_quotas=topic_quotas,
            budget_allocation=budget_allocation,
            cross_channel_themes=themes,
            content_calendar=list(parsed.get("content_calendar") or []),
            risk_assessment=list(parsed.get("risk_assessment") or []),
            success_metrics=dict(parsed.get("success_metrics") or {}),
            portfolio_plan=portfolio_plan,
            emphasize_distribution=emphasize,
            raw_provider_text=raw_text,
            provider_usage=usage,
        )
