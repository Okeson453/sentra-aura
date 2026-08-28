"""Prompt injection defense for SentraAura.

Architecture §41.4: untrusted boundary tagging, sanitization,
classification of retrieved content as DATA never instruction.
"""
from __future__ import annotations

import re
from typing import Any

from sentinel_exceptions import PromptInjectionDetected


# Known injection patterns (heuristic layer)
_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(the\s+)?system\s+prompt", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+.*?(ignore|bypass|override)", re.IGNORECASE),
    re.compile(r"DAN\s*mode", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"\[system\s*override\]", re.IGNORECASE),
    re.compile(r"\{\{.*?\}\}", re.IGNORECASE),  # Template injection attempts
    re.compile(r"`{3,}.*?`{3,}", re.DOTALL),  # Code block injection
]


class InjectionClassifier:
    """Classify text for prompt-injection risk."""

    def __init__(self, threshold: float = 0.7) -> None:
        self.threshold = threshold

    def classify(self, text: str) -> dict[str, Any]:
        """Return classification result with score and flagged patterns."""
        score = 0.0
        flagged: list[str] = []

        for pattern in _INJECTION_PATTERNS:
            if pattern.search(text):
                score += 0.15
                flagged.append(pattern.pattern[:50])

        # Additional heuristics
        if text.count("\n") > 20 and "instruction" in text.lower():
            score += 0.1
        if len(text) > 2000 and "system" in text.lower():
            score += 0.05

        score = min(score, 1.0)
        return {
            "score": score,
            "is_injection": score >= self.threshold,
            "flagged_patterns": flagged,
        }

    def raise_if_injection(self, text: str, context: str = "") -> None:
        """Raise PromptInjectionDetected if text scores above threshold."""
        result = self.classify(text)
        if result["is_injection"]:
            raise PromptInjectionDetected(
                f"Prompt injection detected in {context}",
                details={"score": result["score"], "patterns": result["flagged_patterns"]},
            )


def sanitize_untrusted_input(text: str) -> str:
    """Sanitize untrusted input by escaping control characters and tagging.

    Tags retrieved content as DATA per Architecture §41.4.
    """
    # Escape XML/HTML-like tags to prevent rendering tricks
    text = text.replace("<", "&lt;").replace(">", "&gt;")
    # Escape backticks to prevent markdown/code injection
    text = text.replace("`", "\\`")
    # Add DATA boundary tag
    return f"[DATA_BOUNDARY]\n{text}\n[/DATA_BOUNDARY]"
