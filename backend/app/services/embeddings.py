"""Text embedding providers for semantic similarity.

Production uses fastembed's ONNX ``all-MiniLM-L6-v2`` (384 dims). Tests use
a deterministic hashing stand-in so the suite stays hermetic and offline.
"""

from __future__ import annotations

import hashlib
from typing import Protocol, runtime_checkable

from app.core.settings import get_settings

EMBEDDING_DIM = 384


@runtime_checkable
class EmbeddingProvider(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """One vector per input text, order preserved."""
        ...


class FastEmbedProvider:
    """ONNX MiniLM-L6-v2 via fastembed; weights load lazily on first use.

    The model file itself is baked into the image at build time
    (FASTEMBED_CACHE_PATH), so initialization never touches the network.
    """

    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = model_name or get_settings().embedding_model_name
        self._model = None

    def _ensure_model(self):
        if self._model is None:
            from fastembed import TextEmbedding  # heavy import, deferred

            self._model = TextEmbedding(model_name=self._model_name)
        return self._model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return [vector.tolist() for vector in self._ensure_model().embed(list(texts))]


class HashingFakeProvider:
    """Deterministic offline stand-in: identical text yields an identical vector."""

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self.dim = dim

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._one(text) for text in texts]

    def _one(self, text: str) -> list[float]:
        values: list[float] = []
        round_index = 0
        while len(values) < self.dim:
            digest = hashlib.sha256(f"{text}#{round_index}".encode("utf-8")).digest()
            values.extend(byte / 255.0 * 2.0 - 1.0 for byte in digest)
            round_index += 1
        return values[: self.dim]
