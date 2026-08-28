"""Content Strategist & Ideation Agent — ContentStrategy + concepts via provider-gateway (§4.2)."""
from __future__ import annotations

import logging
from typing import Any

from agent_runtime.agents.base import BaseAgent
from agent_runtime.sandbox.runner import SandboxLimits
from agent_runtime.envelope import AgentMessageEnvelope

from agent_runtime.agents.creative.content_strategist_ideation_agent.config import (
    ContentStrategistConfig,
)
from agent_runtime.agents.creative.content_strategist_ideation_agent.schemas import (
    ContentStrategy,
    IdeationRequest,
    IdeationResponse,
    TopicPortfolioItem,
    VideoConcept,
)
from agent_runtime.agents.creative.content_strategist_ideation_agent.state import CSIPhase, CSIState
from agent_runtime.agents.creative.content_strategist_ideation_agent import tools as csi_tools
from agent_runtime.agents.creative.content_strategist_ideation_agent.tools import (
    concepts_from_parsed,
    generate_concepts,
    score_ideas,
    try_parse_json_object,
)

logger = logging.getLogger(__name__)


class ContentStrategistIdeationAgent(BaseAgent[IdeationResponse]):
    """Converts market/research intel into topic plan, concepts, and hooks."""

    def __init__(self, config: ContentStrategistConfig | None = None, **kwargs: Any) -> None:
        limits = kwargs.pop("sandbox_limits", None) or SandboxLimits(allow_network=True, max_cpu_time_seconds=60.0)
        super().__init__(
            agent_id="content_strategist_ideation_agent",
            name="Content Strategist & Ideation",
            domain="creative",
            version="1.0.0",
            autonomy_level="L2",
            sandbox_limits=limits,
            **kwargs,
        )
        self.config = config or ContentStrategistConfig()
        self.register_tool("generate_concepts", csi_tools.generate_concepts)
        self.register_tool("score_ideas", csi_tools.score_ideas)

    @property
    def capabilities(self) -> list[str]:
        return [
            "concept_generation",
            "thumbnail_ideation",
            "seo_optimization",
            "trend_alignment",
            "generate_concepts",
            "score_ideas",
        ]

    async def execute(self, envelope: AgentMessageEnvelope) -> dict[str, Any]:
        payload = envelope.message.payload or {}
        if "task_type" not in payload and getattr(envelope.message, "task_type", None):
            payload = {**payload, "task_type": envelope.message.task_type}

        request = IdeationRequest(**payload)
        state = CSIState()
        state.advance(CSIPhase.GENERATING)

        request.topic = self.sanitize_input(request.topic, source="topic")
        request.channel_name = self.sanitize_input(
            request.channel_name, source="channel_name"
        )
        request.target_audience = self.sanitize_input(
            request.target_audience, source="target_audience"
        )

        llm = await self.invoke_tool("generate_concepts", (), {"request": request, "config": self.config})
        state.provider_texts.append(llm.content)
        usage = {
            "prompt_tokens": llm.prompt_tokens,
            "completion_tokens": llm.completion_tokens,
            "total_tokens": llm.total_tokens,
            "estimated_cost_usd": llm.cost_usd,
        }
        state.provider_usages.append(usage)

        parsed = try_parse_json_object(llm.content) or {}
        concepts = concepts_from_parsed(parsed, request.topic)

        state.advance(CSIPhase.SCORING)
        concepts = await self.invoke_tool("score_ideas", (), {"concepts": concepts, "topic": request.topic, "config": self.config})

        response = self._build_response(request, concepts, parsed, llm.content, usage)
        state.advance(CSIPhase.COMPLETED)
        logger.info(
            "ContentStrategist topic=%s concepts=%d",
            request.topic,
            len(response.concepts),
        )
        return response.model_dump()

    def _build_response(
        self,
        request: IdeationRequest,
        concepts: list[VideoConcept],
        parsed: dict[str, Any],
        raw_text: str,
        usage: dict[str, Any],
    ) -> IdeationResponse:
        recommended = concepts[0] if concepts else None
        if parsed.get("recommended_concept") and isinstance(parsed["recommended_concept"], dict):
            try:
                recommended = VideoConcept(**{
                    **(recommended.model_dump() if recommended else {}),
                    **parsed["recommended_concept"],
                })
            except Exception:
                pass

        strategy_raw = parsed.get("content_strategy") or {}
        if isinstance(strategy_raw, str):
            strategy = ContentStrategy(summary=strategy_raw, pillars=list(request.content_pillars))
        else:
            strategy = ContentStrategy(
                summary=str(
                    strategy_raw.get("summary")
                    or parsed.get("strategy_summary")
                    or f"Content strategy for '{request.topic}' on {request.channel_name or 'channel'}."
                ),
                pillars=list(
                    strategy_raw.get("pillars") or request.content_pillars or []
                ),
                series_opportunities=list(strategy_raw.get("series_opportunities") or []),
                brand_constraints_checked=bool(
                    strategy_raw.get("brand_constraints_checked", True)
                ),
            )

        portfolio: list[TopicPortfolioItem] = []
        for i, item in enumerate(parsed.get("topic_portfolio") or []):
            if isinstance(item, dict):
                portfolio.append(
                    TopicPortfolioItem(
                        topic=str(item.get("topic") or request.topic),
                        priority=int(item.get("priority") or i + 1),
                        pillar=str(item.get("pillar") or ""),
                        planned_formats=list(item.get("planned_formats") or ["long-form"]),
                    )
                )
        if not portfolio and request.topic:
            portfolio = [
                TopicPortfolioItem(
                    topic=request.topic,
                    priority=1,
                    pillar=(request.content_pillars[0] if request.content_pillars else ""),
                    planned_formats=["long-form"],
                )
            ]

        idea_set = list(parsed.get("idea_set") or [c.title for c in concepts])
        hooks = list(
            parsed.get("hook_candidates") or [c.hook for c in concepts if c.hook]
        )
        seo = list(parsed.get("seo_optimization_notes") or [])
        if not seo and request.topic:
            seo = [
                f"Target primary keyword: '{request.topic.lower()}'",
                "Include long-tail variations in description",
            ]

        # Handoff shape for scripting_agent.ScriptRequest
        handoff: dict[str, Any] = {}
        if recommended:
            handoff = {
                "video_title": recommended.title,
                "channel_name": request.channel_name,
                "audience_profile": request.target_audience,
                "target_keywords": recommended.target_keywords,
                "tone": "conversational and informative",
                "research_brief": request.research_brief
                if isinstance(request.research_brief, dict)
                else {"text": request.research_brief},
            }

        return IdeationResponse(
            concepts=concepts,
            recommended_concept=recommended,
            content_strategy=strategy,
            topic_portfolio=portfolio,
            idea_set=idea_set,
            hook_candidates=hooks,
            content_series_potential=bool(
                parsed.get("content_series_potential", len(concepts) >= 3)
            ),
            seo_optimization_notes=seo,
            scripting_handoff=handoff,
            raw_provider_text=raw_text,
            provider_usage=usage,
        )
