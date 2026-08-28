from __future__ import annotations
import logging
from typing import Any
from agent_runtime.agents.base import BaseAgent
from agent_runtime.envelope import AgentMessageEnvelope
from agent_runtime.sandbox.runner import SandboxLimits
from agent_runtime.agents.operations.optimization_agent.config import AgentConfig
from agent_runtime.agents.operations.optimization_agent.schemas import AgentRequest, AgentResponse
from agent_runtime.agents.operations.optimization_agent.state import OptimizationPhase, OptimizationState
from agent_runtime.agents.operations.optimization_agent import tools as T

logger = logging.getLogger(__name__)

class OptimizationAgent(BaseAgent[AgentResponse]):
    def __init__(self, config: AgentConfig | None = None, **kwargs: Any) -> None:
        limits = kwargs.pop("sandbox_limits", None) or SandboxLimits(allow_network=True, max_cpu_time_seconds=60.0)
        super().__init__(
            agent_id="optimization_agent",
            name="Optimization Agent",
            domain="operations",
            version="1.0.0",
            autonomy_level="L2",
            sandbox_limits=limits,
            **kwargs,
        )
        self.config = config or AgentConfig()
        self.register_tool("optimize", T.optimize)

    @property
    def capabilities(self) -> list[str]:
        return ['optimize']

    async def execute(self, envelope: AgentMessageEnvelope) -> dict[str, Any]:
        payload = envelope.message.payload or {}
        request = AgentRequest(**payload)
        st = OptimizationState()
        st.advance(OptimizationPhase.RUNNING)
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
            "optimize",
            (),
            {"payload": payload_in, "config": self.config},
        )

        st.record_provider(str(result.get("raw") or ""), result.get("usage"))
        st.advance(OptimizationPhase.COMPLETED)
        return AgentResponse(
            status=str(result.get("status") or "ok"),
            result=result,
            artifacts=list(result.get("artifacts") or []),
            raw_provider_text=str(result.get("raw") or "")[:2000],
            provider_usage=result.get("usage"),
        ).model_dump()
