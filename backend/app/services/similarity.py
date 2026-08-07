from __future__ import annotations

from numpy import ndarray
from scipy.sparse import csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DEFAULT_TOP_K = 5
_MIN_NONZERO_SCORE = 0.0


def build_tfidf_matrix(texts: list[str]) -> csr_matrix:
    """TF-IDF matrix for the given documents (rows aligned with ``texts``)."""
    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 2),
        min_df=1,
    )
    return vectorizer.fit_transform(texts)


def find_top_similar(matrix: csr_matrix, top_k: int = DEFAULT_TOP_K) -> list[tuple[int, int, float]]:
    """Top-k most similar (i, j, score) triples, excluding self and score==0.

    Deterministic: ties broken by (score DESC, j ASC).
    """
    n = matrix.shape[0]
    if n < 2:
        return []

    sim: ndarray = cosine_similarity(matrix)
    for i in range(n):
        sim[i, i] = _MIN_NONZERO_SCORE  # exclude self

    triples: list[tuple[int, int, float]] = []
    for i in range(n):
        row = sim[i]
        candidates = [j for j in range(n) if row[j] > _MIN_NONZERO_SCORE]
        candidates.sort(key=lambda j: (-row[j], j))
        for j in candidates[:top_k]:
            triples.append((i, j, float(row[j])))
    return triples