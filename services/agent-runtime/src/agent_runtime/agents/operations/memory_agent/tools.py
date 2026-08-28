from __future__ import annotations
import logging
from typing import Any
from agent_runtime.agents.operations.memory_agent.config import AgentConfig as AgentConfig

logger = logging.getLogger(__name__)

_MEM: dict[str, list[dict[str, Any]]] = {}

async def store_memory(payload: dict[str, Any], *, config: AgentConfig) -> dict[str, Any]:
    """Store channel memory entries keyed by channel_id."""
    channel = str(payload.get("channel_id") or (payload.get("metadata") or {}).get("channel_id") or "default")
    entry = {"text": str(payload.get("text") or payload.get("topic") or ""), "tags": payload.get("tags") or []}
    _MEM.setdefault(channel, []).append(entry)
    return {"status": "ok", "tool": "store_memory", "channel_id": channel, "count": len(_MEM[channel]),
            "raw": f"stored channel={channel}", "usage": {"total_tokens": 0, "estimated_cost_usd": 0.0}}

async def recall_memory(payload: dict[str, Any], *, config: AgentConfig) -> dict[str, Any]:
    """Recall memory entries, optional tag filter."""
    channel = str(payload.get("channel_id") or (payload.get("metadata") or {}).get("channel_id") or "default")
    tag = (payload.get("tag") or "")
    items = list(_MEM.get(channel) or [])
    if tag:
        items = [i for i in items if tag in (i.get("tags") or [])]
    return {"status": "ok", "tool": "recall_memory", "channel_id": channel, "items": items,
            "raw": f"recalled={len(items)}", "usage": {"total_tokens": 0, "estimated_cost_usd": 0.0}}
