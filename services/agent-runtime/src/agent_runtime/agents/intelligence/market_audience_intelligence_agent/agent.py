"""Market & Audience Intelligence Agent — sole consumer of Data Ingestion Pipeline (§51.1)."""
from __future__ import annotations

import json
import logging
from typing import Any

from agent_runtime.agents.base import BaseAgent
from agent_runtime.sandbox.runner import SandboxLimits
from agent_runtime.envelope import AgentMessageEnvelope

from agent_runtime.agents.intelligence.market_audience_intelligence_agent.config import (
    MarketAudienceConfig,
)
from agent_runtime.agents.intelligence.market_audience_intelligence_agent.schemas import (
    IntelligenceRequest,
    IntelligenceResponse,
    TrendSignal,
)
from agent_runtime.agents.intelligence.market_audience_intelligence_agent.state import (
    MAIPhase,
    MAIState,
)
from agent_runtime.agents.intelligence.market_audience_intelligence_agent import tools as mai_tools
from agent_runtime.agents.intelligence.market_audience_intelligence_agent.tools import (
    analyze_sentiment,
    fetch_trends,
    render_analyze_prompt,
    signals_from_ingestion,
    try_parse_json_object,
)

logger = logging.getLogger(__name__)


class MarketAudienceIntelligenceAgent(BaseAgent[IntelligenceResponse]):
    """Monitors external signals via data-ingestion-pipeline; synthesizes opportunities."""

    def __init__(self, config: MarketAudienceConfig | None = None, **kwargs: Any) -> None:
        limits = kwargs.pop("sandbox_limits", None) or SandboxLimits(allow_network=True, max_cpu_time_seconds=60.0)
        super().__init__(
            agent_id="market_audience_intelligence_agent",
            name="Market & Audience Intelligence",
            domain="intelligence",
            version="1.0.0",
            autonomy_level="L2",
            sandbox_limits=limits,
            **kwargs,
        )
        self.config = config or MarketAudienceConfig()
        # Permission-enforced tools
        self.register_tool("fetch_trends", mai_tools.fetch_trends)
        self.register_tool("analyze_sentiment", mai_tools.analyze_sentiment)

    @property
    def capabilities(self) -> list[str]:
        return [
            "trend_analysis",
            "audience_segmentation",
            "competitor_gap_analysis",
            "keyword_research",
            "fetch_trends",
            "analyze_sentiment",
        ]

    async def execute(self, envelope: AgentMessageEnvelope) -> dict[str, Any]:
        payload = envelope.message.payload or {}
        if "task_type" not in payload and getattr(envelope.message, "task_type", None):
            payload = {**payload, "task_type": envelope.message.task_type}

        request = IntelligenceRequest(**payload)
        state = MAIState()
        state.advance(MAIPhase.FETCHING)

        request.market_segment = self.sanitize_input(
            request.market_segment, source="market_segment"
        )

        # Permission tool: fetch_trends → data-ingestion-pipeline
        jobs = await self.invoke_tool("fetch_trends", (), {"request": request, "config": self.config})
        state.ingestion_jobs = [
            jobs.get("trends_job") or {},
            *([jobs["youtube_job"]] if jobs.get("youtube_job") else []),
            *(jobs.get("competitor_jobs") or []),
        ]
        trend_signals = signals_from_ingestion(jobs, request.market_segment)

        state.advance(MAIPhase.ANALYZING)
        context = {
            "market_segment": request.market_segment,
            "channel_name": (request.channels_of_interest[0] if request.channels_of_interest else "portfolio"),
            "channel_niche": request.market_segment,
            "date_range": f"last {request.time_window_days} days",
            "channels_of_interest": request.channels_of_interest,
            "competitor_channels": request.competitor_channels,
            "time_window_days": request.time_window_days,
            "depth": request.depth,
            "trend_data": json.dumps([t.model_dump() for t in trend_signals]),
            "trend_signals": [t.model_dump() for t in trend_signals],
            "ingestion_jobs": state.ingestion_jobs,
            "competitor_data": json.dumps(request.competitor_channels),
        }
        prompt = render_analyze_prompt(context)
        # Permission tool: analyze_sentiment → provider-gateway synthesis
        llm = await self.invoke_tool("analyze_sentiment", (), {"prompt": prompt, "config": self.config})
        state.provider_texts.append(llm.content)
        usage = {
            "prompt_tokens": llm.prompt_tokens,
            "completion_tokens": llm.completion_tokens,
            "total_tokens": llm.total_tokens,
            "estimated_cost_usd": llm.cost_usd,
        }
        state.provider_usages.append(usage)

        parsed = try_parse_json_object(llm.content) or {}
        response = self._build_response(request, trend_signals, parsed, llm.content, usage, state)
        state.advance(MAIPhase.COMPLETED)
        logger.info(
            "MarketAudienceIntelligence segment=%s trends=%d",
            request.market_segment,
            len(response.top_trends),
        )
        return response.model_dump()

    def _build_response(
        self,
        request: IntelligenceRequest,
        signals: list[TrendSignal],
        parsed: dict[str, Any],
        raw_text: str,
        usage: dict[str, Any],
        state: MAIState,
    ) -> IntelligenceResponse:
        # Prefer provider-ranked trends when structured; else pipeline signals
        top_trends = signals
        if parsed.get("top_trends"):
            merged: list[TrendSignal] = []
            for item in parsed["top_trends"]:
                if not isinstance(item, dict):
                    continue
                merged.append(
                    TrendSignal(
                        topic=str(item.get("topic") or request.market_segment),
                        velocity=float(item.get("velocity") or 0.0),
                        saturation=float(item.get("saturation") or 0.0),
                        opportunity_score=float(
                            item.get("opportunity_score")
                            or (float(item.get("velocity") or 0) * 100)
                        ),
                        confidence=str(item.get("confidence") or "medium"),
                        volume=int(item.get("volume") or 0),
                        source=str(item.get("source") or "provider_synthesis"),
                    )
                )
            if merged:
                top_trends = merged

        opportunity_scores = parsed.get("opportunity_scores") or [
            {
                "topic": t.topic,
                "score": t.opportunity_score,
                "confidence": t.confidence,
            }
            for t in top_trends
        ]

        summary = str(
            parsed.get("market_summary")
            or (
                f"Intelligence for {request.market_segment}: "
                f"{len(top_trends)} trend signals from data-ingestion-pipeline. "
                f"{raw_text[:240]}"
            )
        )

        return IntelligenceResponse(
            market_summary=summary,
            top_trends=top_trends,
            opportunity_scores=opportunity_scores,
            audience_segments=list(parsed.get("audience_segments") or []),
            competitor_gaps=list(parsed.get("competitor_gaps") or []),
            keyword_opportunities=list(parsed.get("keyword_opportunities") or []),
            content_recommendations=list(parsed.get("content_recommendations") or []),
            confidence_assessment=dict(
                parsed.get("confidence_assessment")
                or {
                    "trend_data": "medium",
                    "audience_data": "low",
                    "competitor_data": "medium" if request.competitor_channels else "low",
                }
            ),
            ingestion_jobs=state.ingestion_jobs,
            raw_provider_text=raw_text,
            provider_usage=usage,
        )
