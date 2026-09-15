from __future__ import annotations

import logging
import time
from typing import Any

from agent_runtime.agents.distribution.community_engagement_agent.config import AgentConfig as AgentConfig

logger = logging.getLogger(__name__)

# Process-local cooldown to prevent reply storms / loops (P4-15).
# Keyed by (channel_id, comment_id). Not a distributed lock — sufficient for
# single-runtime anti-loop; durable state should also track last_reply_at.
_REPLY_COOLDOWN: dict[str, float] = {}
_DEFAULT_COOLDOWN_SECONDS = 3600.0


def _cooldown_key(channel_id: str, comment_id: str) -> str:
    return f"{channel_id}:{comment_id}"


def _under_cooldown(channel_id: str, comment_id: str, cooldown_seconds: float) -> bool:
    key = _cooldown_key(channel_id, comment_id)
    last = _REPLY_COOLDOWN.get(key)
    if last is None:
        return False
    return (time.time() - last) < cooldown_seconds


def _mark_replied(channel_id: str, comment_id: str) -> None:
    _REPLY_COOLDOWN[_cooldown_key(channel_id, comment_id)] = time.time()


async def engage_comments(payload: dict[str, Any], *, config: AgentConfig) -> dict[str, Any]:
    """
    Comment engagement drafts. Policy: engage_comments is ESCALATE because it posts
    publicly under the channel identity (live external state mutation).

    P4-15: skip comments already replied to within cooldown window to prevent reply loops.
    """
    comments = payload.get("comments") or (payload.get("content") or {}).get("comments") or []
    channel_id = str(payload.get("channel_id") or payload.get("channel") or "default")
    cooldown = float(getattr(config, "reply_cooldown_seconds", _DEFAULT_COOLDOWN_SECONDS) or _DEFAULT_COOLDOWN_SECONDS)

    replies = []
    skipped_cooldown = []
    for i, c in enumerate(comments if isinstance(comments, list) else []):
        if not isinstance(c, dict):
            continue
        comment_id = str(c.get("id") or f"c-{i}")
        if _under_cooldown(channel_id, comment_id, cooldown):
            skipped_cooldown.append(comment_id)
            continue
        text = str(c.get("text") or "")
        tone = "thanks" if any(w in text.lower() for w in ("great", "love", "thanks")) else "clarify"
        topic = str(payload.get("topic") or "")
        draft = (
            f"Thanks for watching our take on {topic}!"
            if tone == "thanks"
            else f"Good question about {topic} — we cover that in the video."
        )
        replies.append({
            "comment_id": comment_id,
            "draft_reply": draft,
            "tone": tone,
            "status": "draft_pending_approval",
        })
        _mark_replied(channel_id, comment_id)

    if not replies and not skipped_cooldown:
        topic = str(payload.get("topic") or "this video")
        replies = [{
            "comment_id": "none",
            "draft_reply": f"Thanks for the feedback on {topic}!",
            "status": "draft_pending_approval",
        }]

    return {
        "status": "ok",
        "tool": "engage_comments",
        "replies": replies,
        "skipped_cooldown": skipped_cooldown,
        "policy": "ESCALATE_required_before_post",
        "artifacts": replies,
        "raw": f"replies={len(replies)} skipped_cooldown={len(skipped_cooldown)}",
        "usage": {"total_tokens": 0, "estimated_cost_usd": 0.0},
    }
