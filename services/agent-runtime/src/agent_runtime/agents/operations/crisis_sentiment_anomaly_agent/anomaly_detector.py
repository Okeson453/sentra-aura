from __future__ import annotations
from typing import Any

def detect_anomalies(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload or {}
    text = str(payload.get("text") or payload.get("comments") or "")
    score = 0.9 if any(w in text.lower() for w in ("scandal", "boycott", "crisis")) else 0.1
    return {"anomaly_score": score, "flagged": score > 0.5, "invoked": True, "signals": []}
