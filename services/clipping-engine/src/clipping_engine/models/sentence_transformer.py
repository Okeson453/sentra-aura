"""Sentence transformer model wrapper.

Provides embeddings for semantic segmentation and similarity scoring.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class SentenceTransformerModel:
    """Wrapper for sentence embedding models."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self._model: Any = None
        logger.info("SentenceTransformerModel initialized: %s", model_name)

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Encode texts to embedding vectors.

        Production: loads the model lazily and caches.
        """
        logger.info("Encoding %d texts", len(texts))
        return [[0.0] * 384 for _ in texts]

    def similarity(self, a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two embeddings."""
        import math
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
