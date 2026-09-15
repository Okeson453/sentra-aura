"""Prompt injection defense for SentraAura.

Architecture §41.4: untrusted boundary tagging, sanitization,
classification of retrieved content as DATA never instruction.
Expanded pattern set addresses research_agent false-negative class (P4-07).
"""
from __future__ import annotations

import re
from typing import Any

from sentinel_exceptions import PromptInjectionDetected


# Known injection patterns (heuristic layer) — layered scoring, not single-regex bypass
_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(the\s+)?(system\s+)?(prompt|instructions?)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+.*?(ignore|bypass|override|unrestricted)", re.IGNORECASE),
    re.compile(r"DAN\s*mode", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"\[system\s*override\]", re.IGNORECASE),
    re.compile(r"\{\{.*?\}\}", re.IGNORECASE),  # Template injection attempts
    re.compile(r"`{3,}.*?`{3,}", re.DOTALL),  # Code block injection
    # Expanded (P4-07 false-negative coverage)
    re.compile(r"forget\s+(everything|your\s+rules|prior\s+context)", re.IGNORECASE),
    re.compile(r"new\s+instructions?\s*:", re.IGNORECASE),
    re.compile(r"do\s+not\s+follow\s+(the\s+)?(system|developer|original)", re.IGNORECASE),
    re.compile(r"override\s+(safety|policy|guardrails?)", re.IGNORECASE),
    re.compile(r"act\s+as\s+(if\s+)?(you\s+have\s+)?no\s+(restrictions?|limits?|guidelines?)", re.IGNORECASE),
    re.compile(r"developer\s+mode\s+(enabled|on)", re.IGNORECASE),
    re.compile(r"sudo\s+mode", re.IGNORECASE),
    re.compile(r"reveal\s+(your\s+)?(system\s+)?prompt", re.IGNORECASE),
    re.compile(r"print\s+(your\s+)?(hidden\s+)?instructions?", re.IGNORECASE),
    re.compile(r"</?\s*system\s*>", re.IGNORECASE),
    re.compile(r"BEGIN\s+SYSTEM\s+PROMPT", re.IGNORECASE),
]


class InjectionClassifier:
    """Classify text for prompt-injection risk."""

    def __init__(self, threshold: float = 0.5) -> None:
        # Slightly lower default threshold after pattern expansion (P4-07)
        self.threshold = threshold

    def classify(self, text: str) -> dict[str, Any]:
        """Return classification result with score and flagged patterns."""
        if not text:
            return {"score": 0.0, "is_injection": False, "flagged_patterns": []}

        score = 0.0
        flagged: list[str] = []

        for pattern in _INJECTION_PATTERNS:
            if pattern.search(text):
                score += 0.28
                flagged.append(pattern.pattern[:60])

        # Additional heuristics
        lower = text.lower()
        if text.count("\n") > 20 and "instruction" in lower:
            score += 0.1
        if len(text) > 2000 and "system" in lower:
            score += 0.05
        # Role-play + instruction combination
        if re.search(r"\b(pretend|roleplay|role-play)\b", lower) and re.search(
            r"\b(ignore|bypass|override)\b", lower
        ):
            score += 0.2
            flagged.append("roleplay+override")

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
    text = text.replace("<", "&lt;").replace(">", "&gt;")
    text = text.replace("`", "\\`")
    return f"[DATA_BOUNDARY]\n{text}\n[/DATA_BOUNDARY]"
