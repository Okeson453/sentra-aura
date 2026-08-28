from __future__ import annotations
import logging
from typing import Any
from agent_runtime.agents.distribution.community_engagement_agent.config import AgentConfig as AgentConfig

logger = logging.getLogger(__name__)

async def engage_comments(payload: dict[str, Any], *, config: AgentConfig) -> dict[str, Any]:
    """
    Comment engagement drafts. Policy: engage_comments is ESCALATE because it posts
    publicly under the channel identity (live external state mutation).
    """
    comments = payload.get("comments") or (payload.get("content") or {}).get("comments") or []
    replies = []
    for i, c in enumerate(comments if isinstance(comments, list) else []):
        if not isinstance(c, dict):
            continue
        text = str(c.get("text") or "")
        tone = "thanks" if any(w in text.lower() for w in ("great", "love", "thanks")) else "clarify"
        topic = str(payload.get("topic") or "")
        draft = (f"Thanks for watching our take on {topic}!" if tone == "thanks" else f"Good question about {topic} — we cover that in the video.")
        replies.append({"comment_id": c.get("id") or f"c-{i}", "draft_reply": draft, "tone": tone, "status": "draft_pending_approval"})
    if not replies:
        topic = str(payload.get("topic") or "this video")
        replies = [{"comment_id": "none", "draft_reply": f"Thanks for the feedback on {topic}!", "status": "draft_pending_approval"}]
    return {"status": "ok", "tool": "engage_comments", "replies": replies, "policy": "ESCALATE_required_before_post",
            "artifacts": replies, "raw": f"replies={len(replies)}", "usage": {"total_tokens": 0, "estimated_cost_usd": 0.0}}
