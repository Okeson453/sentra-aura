"""Scripting Agent — Draft → Critique → Rewrite with optional sponsorship injection.

Uses provider-gateway for every LLM step via BaseAgent.invoke_tool (permission-enforced).
Prompt templates live in packages/prompt-registry/prompts/scripting_agent/.
"""
from __future__ import annotations

import logging
from typing import Any

from agent_runtime.agents.base import BaseAgent
from agent_runtime.envelope import AgentMessageEnvelope
from agent_runtime.sandbox.runner import SandboxLimits

from agent_runtime.agents.creative.scripting_agent.config import ScriptingAgentConfig
from agent_runtime.agents.creative.scripting_agent.reflection_loop import (
    finalize_script_payload,
    run_reflection_loop,
)
from agent_runtime.agents.creative.scripting_agent.schemas import (
    ScriptRequest,
    ScriptResponse,
    SponsorshipBrief,
)
from agent_runtime.agents.creative.scripting_agent.sponsorship_injection import inject_sponsorship
from agent_runtime.agents.creative.scripting_agent import tools as scripting_tools

logger = logging.getLogger(__name__)


class ScriptingAgent(BaseAgent[ScriptResponse]):
    """Drafts, critiques, and rewrites video scripts via provider-gateway."""

    def __init__(self, config: ScriptingAgentConfig | None = None, **kwargs: Any) -> None:
        # LLM tools need network egress to provider-gateway
        limits = kwargs.pop("sandbox_limits", None) or SandboxLimits(allow_network=True, max_cpu_time_seconds=60.0)
        super().__init__(
            agent_id="scripting_agent",
            name="Scripting",
            domain="creative",
            version="1.0.0",
            autonomy_level="L2",
            sandbox_limits=limits,
            **kwargs,
        )
        self.config = config or ScriptingAgentConfig()
        # Bind matrix tool names to callables — invoke_tool is the only execution path
        self.register_tool("draft_script", scripting_tools.draft_script)
        self.register_tool("critique_script", scripting_tools.critique_script)
        self.register_tool("rewrite_section", scripting_tools.rewrite_section)

    @property
    def capabilities(self) -> list[str]:
        return [
            "script_draft",
            "script_critique",
            "script_rewrite",
            "retention_optimization",
            "sponsorship_injection",
            "reflection_loop",
            "draft_script",
            "critique_script",
            "rewrite_section",
        ]

    async def execute(self, envelope: AgentMessageEnvelope) -> dict[str, Any]:
        payload = envelope.message.payload or {}
        if "task_type" not in payload and getattr(envelope.message, "task_type", None):
            payload = {**payload, "task_type": envelope.message.task_type}

        request = ScriptRequest(**payload)

        request.video_title = self.sanitize_input(request.video_title, source="video_title")
        request.channel_name = self.sanitize_input(request.channel_name, source="channel_name")
        request.audience_profile = self.sanitize_input(
            request.audience_profile, source="audience_profile"
        )

        if isinstance(payload.get("sponsorship"), dict) and request.sponsorship is None:
            request.sponsorship = SponsorshipBrief(**payload["sponsorship"])

        logger.info(
            "ScriptingAgent starting task_type=%s title=%r gateway=%s",
            request.task_type,
            request.video_title,
            self.config.provider_gateway_url,
        )

        state = await run_reflection_loop(
            request,
            config=self.config,
            invoker=self.invoke_tool,
            max_rounds=request.max_reflection_rounds,
        )

        script = state.rewritten_script or state.draft_script or {}
        if self.config.enable_sponsorship_injection and request.sponsorship:
            script = inject_sponsorship(script, request.sponsorship, state=state)
            if state.rewritten_script is None and state.draft_script is not None:
                state.draft_script = script
            else:
                state.rewritten_script = script

        payload_out = finalize_script_payload(state, request)
        response = ScriptResponse(**payload_out)

        logger.info(
            "ScriptingAgent finished rounds=%d word_count=%d sponsorship=%s cost=%.4f tokens=%d",
            response.reflection_rounds,
            response.word_count,
            response.sponsorship_applied,
            state.cost_accrued_usd,
            state.tokens_consumed,
        )
        return response.model_dump()
