from __future__ import annotations
import logging
from typing import Any
from agent_runtime.agents.base import BaseAgent
from agent_runtime.envelope import AgentMessageEnvelope
from agent_runtime.sandbox.runner import SandboxLimits
from agent_runtime.agents.operations.memory_agent.config import AgentConfig
from agent_runtime.agents.operations.memory_agent.schemas import AgentRequest, AgentResponse
from agent_runtime.agents.operations.memory_agent.state import MemoryPhase, MemoryState
from agent_runtime.agents.operations.memory_agent import tools as T

logger = logging.getLogger(__name__)

class MemoryAgent(BaseAgent[AgentResponse]):
    def __init__(self, config: AgentConfig | None = None, **kwargs: Any) -> None:
        limits = kwargs.pop("sandbox_limits", None) or SandboxLimits(allow_network=True, max_cpu_time_seconds=60.0)
        super().__init__(
            agent_id="memory_agent",
            name="Memory Agent",
            domain="operations",
            version="1.0.0",
            autonomy_level="L2",
            sandbox_limits=limits,
            **kwargs,
        )
        self.config = config or AgentConfig()
        self.register_tool("store_memory", T.store_memory)
        self.register_tool("recall_memory", T.recall_memory)

    @property
    def capabilities(self) -> list[str]:
        return ['store_memory', 'recall_memory']

    async def execute(self, envelope: AgentMessageEnvelope) -> dict[str, Any]:
        payload = envelope.message.payload or {}
        request = AgentRequest(**payload)
        st = MemoryState()
        st.advance(MemoryPhase.RUNNING)
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
            "store_memory",
            (),
            {"payload": payload_in, "config": self.config},
        )

        extra = await self.invoke_tool("recall_memory", (), {"payload": payload_in, "config": self.config})
        result = dict(result)
        result["recall_memory"] = extra

        st.record_provider(str(result.get("raw") or ""), result.get("usage"))
        st.advance(MemoryPhase.COMPLETED)
        return AgentResponse(
            status=str(result.get("status") or "ok"),
            result=result,
            artifacts=list(result.get("artifacts") or []),
            raw_provider_text=str(result.get("raw") or "")[:2000],
            provider_usage=result.get("usage"),
        ).model_dump()
