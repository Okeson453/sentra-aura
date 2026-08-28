"""Voice Agent — TTS narration via provider-gateway /v1/tts (§4.2)."""
from __future__ import annotations

import logging
from typing import Any

from agent_runtime.agents.base import BaseAgent
from agent_runtime.sandbox.runner import SandboxLimits
from agent_runtime.envelope import AgentMessageEnvelope

from agent_runtime.agents.creative.voice_agent.config import VoiceAgentConfig
from agent_runtime.agents.creative.voice_agent.schemas import (
    VoiceRequest,
    VoiceResponse,
    VoiceSegment,
)
from agent_runtime.agents.creative.voice_agent.state import VoicePhase, VoiceState
from agent_runtime.agents.creative.voice_agent import tools as voice_tools
from agent_runtime.agents.creative.voice_agent.tools import (
    extract_script_texts,
    plan_delivery,
    synthesize_speech,
    try_parse_json_object,
)

logger = logging.getLogger(__name__)


class VoiceAgent(BaseAgent[VoiceResponse]):
    """Generate TTS narration with tone, speed, and word-level timing."""

    def __init__(self, config: VoiceAgentConfig | None = None, **kwargs: Any) -> None:
        limits = kwargs.pop("sandbox_limits", None) or SandboxLimits(allow_network=True, max_cpu_time_seconds=60.0)
        super().__init__(
            agent_id="voice_agent",
            name="Voice",
            domain="creative",
            version="1.0.0",
            autonomy_level="L2",
            sandbox_limits=limits,
            **kwargs,
        )
        self.config = config or VoiceAgentConfig()
        self.register_tool("synthesize_speech", voice_tools.synthesize_speech)
        self.register_tool("plan_delivery", voice_tools.plan_delivery)

    @property
    def capabilities(self) -> list[str]:
        return [
            "voiceover_planning",
            "tts_synthesis",
            "pacing_guidance",
            "emotion_mapping",
            "synthesize_speech",
            # clone_voice is ESCALATE in tool_permissions — not auto capability
        ]

    async def execute(self, envelope: AgentMessageEnvelope) -> dict[str, Any]:
        payload = envelope.message.payload or {}
        if "task_type" not in payload and getattr(envelope.message, "task_type", None):
            payload = {**payload, "task_type": envelope.message.task_type}

        request = VoiceRequest(**payload)
        state = VoiceState()

        request.voice_profile = self.sanitize_input(
            request.voice_profile, source="voice_profile"
        )

        # Prefer nested script from full scripting_agent response
        script = request.script
        if request.script_response and isinstance(request.script_response, dict):
            script = request.script_response.get("script") or script

        texts = extract_script_texts(script if isinstance(script, dict) else {})
        if not texts:
            texts = [("main", "Default voiceover placeholder.")]

        state.advance(VoicePhase.PLANNING)
        plan = await self.invoke_tool(
            "plan_delivery",
            (),
            {
                "script": script if isinstance(script, dict) else {},
                "voice_profile": request.voice_profile,
                "language": request.language,
                "pacing": request.pacing,
                "config": self.config,
            },
        )
        usage = {
            "prompt_tokens": plan.prompt_tokens,
            "completion_tokens": plan.completion_tokens,
            "total_tokens": plan.total_tokens,
            "estimated_cost_usd": plan.cost_usd,
        }
        state.record_provider(plan.content, usage)
        parsed = try_parse_json_object(plan.content) or {}
        plan_segments = {
            str(s.get("id") or s.get("section") or i): s
            for i, s in enumerate(parsed.get("segments") or [])
            if isinstance(s, dict)
        }

        state.advance(VoicePhase.SYNTHESIZING)
        segments: list[VoiceSegment] = []
        total_dur = 0.0
        voice_id = (
            (parsed.get("voice_profile_recommendation") or {}).get("voice_id")
            or self.config.default_voice
        )

        for idx, (sec_id, text) in enumerate(texts):
            clean = self.sanitize_input(text, source=f"script.{sec_id}")
            tts = await self.invoke_tool(
                "synthesize_speech",
                (),
                {"text": clean, "voice": str(voice_id), "config": self.config},
            )
            meta = plan_segments.get(sec_id) or plan_segments.get(str(idx)) or {}
            dur = float(tts.get("duration_seconds") or 0.0)
            total_dur += dur
            seg = VoiceSegment(
                id=f"seg-{idx}-{sec_id}",
                text=clean,
                duration_estimate=dur,
                duration_seconds=dur,
                emotion=str(meta.get("emotion") or "neutral"),
                emphasis_words=list(meta.get("emphasis_words") or []),
                phonetic_notes=dict(meta.get("phonetic_notes") or {}),
                pause_instructions=list(meta.get("pause_instructions") or []),
                audio_url=tts.get("audio_url"),
                word_timings=list(tts.get("word_timings") or []),
                tts_provider=str(tts.get("provider") or "provider-gateway"),
            )
            segments.append(seg)
            state.segment_results.append(tts)

        response = VoiceResponse(
            segments=segments,
            voice_profile_recommendation=dict(
                parsed.get("voice_profile_recommendation")
                or {
                    "voice_id": voice_id,
                    "style": request.voice_profile,
                    "language": request.language,
                }
            ),
            pacing_notes=str(
                parsed.get("pacing_notes")
                or f"Maintain {request.pacing} pacing; {len(segments)} segments."
            ),
            consistency_checklist=list(
                parsed.get("consistency_checklist")
                or [
                    "Volume levels consistent across segments",
                    "Emotion transitions smooth between sections",
                ]
            ),
            tts_metadata={
                "voice": voice_id,
                "segment_count": len(segments),
                "provider": segments[0].tts_provider if segments else None,
            },
            total_duration_seconds=round(total_dur, 3),
            raw_provider_text=plan.content,
            provider_usage=usage,
        )
        state.advance(VoicePhase.COMPLETED)
        logger.info("VoiceAgent segments=%d duration=%.2fs", len(segments), total_dur)
        return response.model_dump()
