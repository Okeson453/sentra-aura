"""AI Clipping Agent — detect, score, reconstruct, rank clips (Arch. §4.2 / §6)."""
from __future__ import annotations

import logging
from typing import Any

from agent_runtime.agents.base import BaseAgent
from agent_runtime.envelope import AgentMessageEnvelope
from agent_runtime.sandbox.runner import SandboxLimits

from agent_runtime.agents.clipping.ai_clipping_agent.config import AgentConfig
from agent_runtime.agents.clipping.ai_clipping_agent.schemas import (
    AgentRequest,
    AgentResponse,
    ClipCandidate,
    FeatureScores,
)
from agent_runtime.agents.clipping.ai_clipping_agent.state import ClippingPhase, ClippingState
from agent_runtime.agents.clipping.ai_clipping_agent import tools as T

logger = logging.getLogger(__name__)


class AIClippingAgent(BaseAgent[AgentResponse]):
    def __init__(self, config: AgentConfig | None = None, **kwargs: Any) -> None:
        limits = kwargs.pop("sandbox_limits", None) or SandboxLimits(
            allow_network=True, max_cpu_time_seconds=60.0
        )
        super().__init__(
            agent_id="ai_clipping_agent",
            name="AI Clipping Agent",
            domain="clipping",
            version="1.1.0",
            autonomy_level="L2",
            sandbox_limits=limits,
            **kwargs,
        )
        self.config = config or AgentConfig()
        self.register_tool("select_clips", T.select_clips)

    @property
    def capabilities(self) -> list[str]:
        return ["select_clips", "composite_clip_score", "context_reconstruction", "rank_dedup"]

    async def execute(self, envelope: AgentMessageEnvelope) -> dict[str, Any]:
        payload = envelope.message.payload or {}
        request = AgentRequest(**payload)
        st = ClippingState()
        st.advance(ClippingPhase.INGESTING)

        topic = self.sanitize_input(str(request.topic or ""), source="topic")
        # Sanitize segment texts
        clean_segments = []
        for seg in request.segments:
            data = seg.model_dump() if hasattr(seg, "model_dump") else dict(seg)
            data["text"] = self.sanitize_input(str(data.get("text") or ""), source="segment")
            clean_segments.append(data)

        payload_in: dict[str, Any] = {
            "topic": topic,
            "video_id": request.video_id,
            "channel_id": request.channel_id,
            "segments": clean_segments,
            "content": request.content or {},
            "script": request.script or {},
            "assets": request.assets or [],
            "shots": request.shots or [],
            "metadata": request.metadata or {},
            "min_duration_seconds": request.min_duration_seconds,
            "max_duration_seconds": request.max_duration_seconds,
            "max_clips": request.max_clips,
            "score_threshold": request.score_threshold,
        }

        st.advance(ClippingPhase.SEGMENTING)
        st.advance(ClippingPhase.SCORING)
        st.advance(ClippingPhase.CONTEXT)
        st.advance(ClippingPhase.RANKING)

        result = await self.invoke_tool(
            "select_clips",
            (),
            {"payload": payload_in, "config": self.config},
        )

        st.segment_count = int(result.get("segment_count") or 0)
        candidates_raw = result.get("candidates") or []
        rejected_raw = result.get("rejected") or []
        st.candidate_count = len(candidates_raw) + len(rejected_raw)
        st.selected_count = len(candidates_raw)
        st.record_provider(str(result.get("raw") or ""), result.get("usage"))
        st.advance(ClippingPhase.COMPLETED)

        def _to_candidate(c: dict[str, Any]) -> ClipCandidate:
            scores = c.get("scores") or {}
            if isinstance(scores, FeatureScores):
                fs = scores
            else:
                fs = FeatureScores(**{k: float(scores.get(k, 0.0)) for k in FeatureScores.model_fields})
            return ClipCandidate(
                clip_id=str(c.get("clip_id") or ""),
                video_id=str(c.get("video_id") or request.video_id or ""),
                start_seconds=float(c.get("start_seconds") or 0),
                end_seconds=float(c.get("end_seconds") or 0),
                duration_seconds=float(c.get("duration_seconds") or 0),
                text=str(c.get("text") or ""),
                reconstructed_text=str(c.get("reconstructed_text") or ""),
                scores=fs,
                context_complete=bool(c.get("context_complete")),
                rank=int(c.get("rank") or 0),
                rejected_reason=c.get("rejected_reason"),
            )

        response = AgentResponse(
            status=str(result.get("status") or "ok"),
            video_id=str(result.get("video_id") or request.video_id or ""),
            candidates=[_to_candidate(c) for c in candidates_raw],
            rejected=[_to_candidate(c) for c in rejected_raw],
            segment_count=st.segment_count,
            result=result,
            artifacts=list(result.get("artifacts") or []),
            raw_provider_text=str(result.get("raw") or ""),
            provider_usage=result.get("usage"),
        )
        return response.model_dump()
