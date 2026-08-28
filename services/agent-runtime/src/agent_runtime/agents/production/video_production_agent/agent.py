from __future__ import annotations
import logging
from typing import Any
from agent_runtime.agents.base import BaseAgent
from agent_runtime.envelope import AgentMessageEnvelope
from agent_runtime.sandbox.runner import SandboxLimits
from agent_runtime.agents.production.video_production_agent.config import AgentConfig
from agent_runtime.agents.production.video_production_agent.schemas import AgentRequest, AgentResponse
from agent_runtime.agents.production.video_production_agent.state import VideoProductionPhase, VideoProductionState
from agent_runtime.agents.production.video_production_agent import tools as T

logger = logging.getLogger(__name__)

class VideoProductionAgent(BaseAgent[AgentResponse]):
    def __init__(self, config: AgentConfig | None = None, **kwargs: Any) -> None:
        limits = kwargs.pop("sandbox_limits", None) or SandboxLimits(allow_network=True, max_cpu_time_seconds=60.0)
        super().__init__(
            agent_id="video_production_agent",
            name="Video Production Agent",
            domain="production",
            version="1.0.0",
            autonomy_level="L2",
            sandbox_limits=limits,
            **kwargs,
        )
        self.config = config or AgentConfig()
        self.register_tool("assemble_timeline", T.assemble_timeline)
        self.register_tool("render_video", T.render_video)

    @property
    def capabilities(self) -> list[str]:
        return ['assemble_timeline', 'render_video']

    async def execute(self, envelope: AgentMessageEnvelope) -> dict[str, Any]:
        payload = envelope.message.payload or {}
        request = AgentRequest(**payload)
        st = VideoProductionState()
        st.advance(VideoProductionPhase.RUNNING)
        topic = self.sanitize_input(str(request.topic or ""), source="topic")
        payload_in = {
            "topic": topic,
            "content": request.content or {},
            "script": request.script or {},
            "assets": request.assets or [],
            "shots": request.shots or [],
            "metadata": request.metadata or {},
        }
        result = await self.invoke_tool(
            "assemble_timeline",
            (),
            {"payload": payload_in, "config": self.config},
        )
        result = dict(result)
        render_payload = {
            **payload_in,
            "timeline": result.get("timeline") or [],
        }
        extra = await self.invoke_tool(
            "render_video",
            (),
            {"payload": render_payload, "config": self.config},
        )
        result["render_video"] = extra
        if isinstance(extra, dict):
            result["render_job"] = extra.get("render_job")

        st.record_provider(str(result.get("raw") or ""), result.get("usage"))
        st.advance(VideoProductionPhase.COMPLETED)
        return AgentResponse(
            status=str(result.get("status") or "ok"),
            result=result,
            artifacts=list(result.get("artifacts") or []),
            raw_provider_text=str(result.get("raw") or "")[:2000],
            provider_usage=result.get("usage"),
        ).model_dump()
