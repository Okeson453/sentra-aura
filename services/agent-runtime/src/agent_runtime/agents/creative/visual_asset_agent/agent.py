from __future__ import annotations
import hashlib
import logging
from typing import Any
from agent_runtime.agents.base import BaseAgent
from agent_runtime.sandbox.runner import SandboxLimits
from agent_runtime.envelope import AgentMessageEnvelope
from agent_runtime.agents.creative.visual_asset_agent.config import VisualAssetConfig
from agent_runtime.agents.creative.visual_asset_agent.schemas import VisualAsset, VisualAssetRequest, VisualAssetResponse
from agent_runtime.agents.creative.visual_asset_agent.state import VAPhase, VAState
from agent_runtime.agents.creative.visual_asset_agent import tools as T

logger = logging.getLogger(__name__)


class VisualAssetAgent(BaseAgent[VisualAssetResponse]):
    def __init__(self, config: VisualAssetConfig | None = None, **kwargs: Any) -> None:
        limits = kwargs.pop("sandbox_limits", None) or SandboxLimits(allow_network=True, max_cpu_time_seconds=60.0)
        super().__init__(
            agent_id="visual_asset_agent",
            name="Visual Asset",
            domain="creative",
            version="1.1.0",
            autonomy_level="L2",
            sandbox_limits=limits,
            **kwargs,
        )
        self.config = config or VisualAssetConfig()
        self.register_tool("generate_image", T.generate_image)
        self.register_tool("edit_image", T.edit_image)

    @property
    def capabilities(self) -> list[str]:
        return ["generate_image", "edit_image", "stock_search", "provenance_tracking"]

    async def execute(self, envelope: AgentMessageEnvelope) -> dict[str, Any]:
        payload = envelope.message.payload or {}
        request = VisualAssetRequest(**payload)
        state = VAState()
        state.advance(VAPhase.GENERATING)
        scenes = T.scenes_from_request(request.scene_descriptions, request.script, request.asset_budget)
        if not scenes:
            scenes = ["Brand-safe placeholder scene"]
        assets: list[VisualAsset] = []
        for i, desc in enumerate(scenes[: max(1, request.asset_budget)]):
            desc = self.sanitize_input(str(desc), source=f"scene_{i}")
            prompt = f"{desc}. Style: {request.brand_style or 'clean documentary'}."
            result = await self.invoke_tool(
                "generate_image",
                (),
                {"prompt": prompt, "config": self.config},
            )
            if not isinstance(result, dict):
                result = {"image_url": str(result)}
            aid = hashlib.md5(f"{prompt}{i}".encode(), usedforsecurity=False).hexdigest()[:12]
            assets.append(
                VisualAsset(
                    asset_id=f"va-{aid}",
                    scene_id=f"scene-{i}",
                    prompt=prompt,
                    image_url=str(result.get("image_url") or result.get("url") or ""),
                    source="generated",
                    provenance={"provider": result.get("provider") or "provider-gateway"},
                    brand_compliant=True,
                )
            )
            usage = result.get("usage") if isinstance(result, dict) else None
            if isinstance(usage, dict):
                state.record_cost(
                    float(usage.get("estimated_cost_usd") or 0.0),
                    int(usage.get("total_tokens") or 0),
                )
            else:
                state.record_cost(0.001, 0)
            state.prompts_used.append(prompt)
            state.generated.append({"asset_id": f"va-{aid}", "prompt": prompt})
        state.checkpoint_id = f"va-{len(assets)}"
        state.advance(VAPhase.COMPLETED)
        out = VisualAssetResponse(
            assets=assets,
            manifest={"count": len(assets), "budget": request.asset_budget},
        ).model_dump()
        out["durable_state"] = state.to_dict()
        return out
