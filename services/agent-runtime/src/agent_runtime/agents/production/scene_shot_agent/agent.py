from __future__ import annotations
import logging
from typing import Any
from agent_runtime.agents.base import BaseAgent
from agent_runtime.envelope import AgentMessageEnvelope
from agent_runtime.sandbox.runner import SandboxLimits
from agent_runtime.agents.production.scene_shot_agent.config import AgentConfig
from agent_runtime.agents.production.scene_shot_agent.schemas import AgentRequest, AgentResponse, Shot
from agent_runtime.agents.production.scene_shot_agent.state import ShotPlanPhase, ShotPlanState
from agent_runtime.agents.production.scene_shot_agent import tools as shot_tools

logger = logging.getLogger(__name__)

class SceneShotAgent(BaseAgent[AgentResponse]):
    def __init__(self, config: AgentConfig | None = None, **kwargs: Any) -> None:
        limits = kwargs.pop("sandbox_limits", None) or SandboxLimits(allow_network=True, max_cpu_time_seconds=60.0)
        super().__init__(
            agent_id="scene_shot_agent",
            name="Scene Shot",
            domain="production",
            version="1.0.0",
            autonomy_level="L2",
            sandbox_limits=limits,
            **kwargs,
        )
        self.config = config or AgentConfig()
        self.register_tool("plan_shots", shot_tools.plan_shots)

    @property
    def capabilities(self) -> list[str]:
        return ["plan_shots", "scene_edl", "visual_asset_binding"]

    async def execute(self, envelope: AgentMessageEnvelope) -> dict[str, Any]:
        payload = envelope.message.payload or {}
        request = AgentRequest(**payload)
        state = ShotPlanState()
        state.advance(ShotPlanPhase.INGESTING)

        state.advance(ShotPlanPhase.PLANNING)
        result = await self.invoke_tool(
            "plan_shots",
            (),
            {
                "script": request.script or {},
                "visual_assets": request.visual_assets or [],
                "config": self.config,
            },
        )
        shots_data = result.get("shots") or []
        state.record_provider(str(result.get("raw_text") or ""), result.get("usage"))
        state.shot_count = len(shots_data)

        state.advance(ShotPlanPhase.EDL)
        edl = []
        t = 0.0
        for s in shots_data:
            dur = float(s.get("duration_seconds") or 5)
            edl.append({"shot_id": s["shot_id"], "in": t, "out": t + dur})
            t += dur

        state.advance(ShotPlanPhase.COMPLETED)
        return AgentResponse(
            shots=[Shot(**s) for s in shots_data],
            edl=edl,
            raw_provider_text=str(result.get("raw_text") or "")[:2000],
            provider_usage=result.get("usage"),
        ).model_dump()
