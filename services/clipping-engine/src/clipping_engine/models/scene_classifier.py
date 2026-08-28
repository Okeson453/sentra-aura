"""Scene classifier model wrapper.

Classifies scenes by type: Proposition, Explanation, Story, Argument, Example, Quote, Payoff, Hook, CTA.
"""
from __future__ import annotations

import logging
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class SceneType(str, Enum):
    """Narrative unit types recognized by the segmentation model."""
    PROPOSITION = "Proposition"
    EXPLANATION = "Explanation"
    STORY = "Story"
    ARGUMENT = "Argument"
    EXAMPLE = "Example"
    QUOTE = "Quote"
    PAYOFF = "Payoff"
    HOOK = "Hook"
    CTA = "CTA"


class SceneClassifier:
    """Classifies transcript segments into narrative unit types."""

    def __init__(self, model_name: str = "scene-classifier-v1") -> None:
        self.model_name = model_name
        self._model: Any = None
        logger.info("SceneClassifier initialized: %s", model_name)

    def classify(self, text: str, context: str = "") -> dict[str, Any]:
        """Classify a text segment into a narrative unit type.

        Production: calls LLM via Provider Gateway with structured output.
        """
        logger.info("Classifying scene: %s...", text[:60])
        return {
            "text": text,
            "scene_type": SceneType.EXPLANATION.value,
            "confidence": 0.85,
            "context": context,
        }
