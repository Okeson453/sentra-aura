from __future__ import annotations
import logging
from typing import Any
from agent_runtime.agents.distribution.seo_packaging_agent.config import AgentConfig

logger = logging.getLogger(__name__)

async def package_seo(payload: dict[str, Any], *, config: AgentConfig) -> dict[str, Any]:
    """Titles, description, tags from topic + script."""
    topic = str(payload.get("topic") or "Content")
    script = payload.get("script") or {}
    hook = str(script.get("hook") or topic)
    titles = [
        f"{hook[:60]}",
        f"{topic}: What You Need to Know",
        f"The Truth About {topic}"[:70],
    ]
    tags = list({w.lower().strip(".,?!") for w in (topic + " " + hook).split() if len(w) > 3})[:12]
    description = f"{hook}\n\nIn this video we cover {topic}.\n\n" + " ".join(f"#{t}" for t in tags[:5])
    return {"status": "ok", "tool": "package_seo", "titles": titles, "description": description, "tags": tags,
            "artifacts": [{"type": "seo_package", "titles": titles}], "raw": f"titles={len(titles)} tags={len(tags)}",
            "usage": {"total_tokens": 0, "estimated_cost_usd": 0.0}}
