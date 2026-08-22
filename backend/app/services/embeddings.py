"""Text embedding providers for semantic similarity.

Production uses fastembed's ONNX ``all-MiniLM-L6-v2`` (384 dims). Tests use
a deterministic hashing stand-in so the suite stays hermetic and offline.
"""

from __future__ import annotations

import hashlib
from typing import Protocol, runtime_checkable

from sqlalchemy import select, text

from app.core.settings import get_settings
from app.models import Paper

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
        return [self._one(content) for content in texts]

    def _one(self, text_str: str) -> list[float]:
        values: list[float] = []
        round_index = 0
        while len(values) < self.dim:
            digest = hashlib.sha256(f"{text_str}#{round_index}".encode("utf-8")).digest()
            values.extend(byte / 255.0 * 2.0 - 1.0 for byte in digest)
            round_index += 1
        return values[: self.dim]


def paper_text(title: str | None, abstract: str | None) -> str:
    """Combined embedding input; empty string when neither field has content."""
    parts = [part.strip() for part in (title, abstract) if part and part.strip()]
    return " ".join(parts)


def vector_literal(vector: list[float]) -> str:
    """pgvector text format: ``[0.5,-1,...]`` (also stored as TEXT on SQLite tests)."""
    return "[" + ",".join(f"{component:.7g}" for component in vector) + "]"


def upsert_embeddings(session, records: list[tuple[int, list[float]]]) -> int:
    """Insert or update one paper_embedding row per (paper_id, vector)."""
    written = 0
    for paper_id, vector in records:
        session.execute(
            text(
                "INSERT INTO paper_embedding (paper_id, embedding) "
                "VALUES (:pid, :emb) "
                "ON CONFLICT (paper_id) DO UPDATE SET embedding = EXCLUDED.embedding"
            ),
            {"pid": paper_id, "emb": vector_literal(vector)},
        )
        written += 1
    return written


def embed_papers_by_ids(session, provider: EmbeddingProvider, paper_ids: list[int]) -> int:
    """Embed title+abstract for the given papers and persist their vectors.

    Papers without usable text are skipped (no row), matching backfill and
    snapshot semantics. Returns the number of vectors written.
    """
    if not paper_ids:
        return 0
    rows = session.execute(
        select(Paper.id, Paper.title, Paper.abstract).where(Paper.id.in_(list(paper_ids)))
    ).all()
    texts = [paper_text(row.title, row.abstract) for row in rows]
    pairs = [
        (row.id, vector)
        for row, text_content, vector in zip(rows, texts, provider.embed_texts(texts))
        if text_content
    ]
    return upsert_embeddings(session, pairs)
