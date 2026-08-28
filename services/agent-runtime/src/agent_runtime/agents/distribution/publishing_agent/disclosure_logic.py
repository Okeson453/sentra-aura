from __future__ import annotations
from typing import Any

def apply_disclosure(metadata: dict[str, Any] | None, content: dict[str, Any] | None) -> dict[str, Any]:
    metadata = metadata or {}
    content = content or {}
    synthetic = bool(metadata.get("synthetic") or metadata.get("ai_generated") or content.get("synthetic"))
    sponsored = bool(metadata.get("sponsored") or content.get("sponsorship"))
    return {
        "altered_or_synthetic_content": synthetic,
        "sponsored_disclosure": sponsored,
        "tags": (["#ad"] if sponsored else []) + (["#AIgenerated"] if synthetic else []),
        "invoked": True,
    }
