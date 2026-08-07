import pytest

from app.services.similarity import build_tfidf_matrix, find_top_similar

CORPUS = [
    "transformer attention neural network language model",
    "attention mechanism neural network positional encoding",
    "convolutional neural network image classification object detection",
    "object detection bounding boxes convolution residual",
]


def test_empty_corpus_produces_no_pairs():
    matrix = build_tfidf_matrix([])
    assert find_top_similar(matrix) == []


def test_single_document_produces_no_pairs():
    matrix = build_tfidf_matrix(["only one paper here"])
    assert find_top_similar(matrix) == []


def test_all_empty_texts_produces_no_pairs():
    matrix = build_tfidf_matrix(["", "", ""])
    assert find_top_similar(matrix) == []


def test_all_stopwords_produces_no_pairs():
    matrix = build_tfidf_matrix(["the of and", "and the of"])
    assert find_top_similar(matrix) == []


def test_self_is_excluded_and_scores_bounded():
    matrix = build_tfidf_matrix(CORPUS)
    triples = find_top_similar(matrix)
    assert triples
    for i, j, score in triples:
        assert i != j
        assert 0.0 < score <= 1.0


def test_top_k_respected_per_paper():
    matrix = build_tfidf_matrix(CORPUS)
    for k in (1, 2, 3):
        triples = find_top_similar(matrix, top_k=k)
        per_paper = {}
        for i, j, _ in triples:
            per_paper.setdefault(i, []).append(j)
        assert max(len(v) for v in per_paper.values()) <= k


def test_every_paper_can_have_a_neighbor_when_kis_large():
    matrix = build_tfidf_matrix(CORPUS)
    triples = find_top_similar(matrix, top_k=10)
    sources = {i for i, _, _ in triples}
    assert sources == {0, 1, 2, 3}


def test_strongest_pair_is_first_and_deterministic():
    matrix = build_tfidf_matrix(CORPUS)
    first_run = find_top_similar(matrix)
    second_run = find_top_similar(matrix)
    assert first_run == second_run
    assert max(first_run, key=lambda t: t[2]) in first_run


def test_duplicate_titles_are_identical_scores():
    matrix = build_tfidf_matrix(["alpha beta gamma", "alpha beta gamma", "delta epsilon"])
    triples = find_top_similar(matrix, top_k=10)
    pairs = {(a, b): s for a, b, s in triples}
    assert pairs[(0, 1)] == pytest.approx(1.0)
    assert pairs[(1, 0)] == pytest.approx(1.0)


def test_scores_deterministic_across_independent_builds():
    a = build_tfidf_matrix(["one two three four", "one two purple green"])
    b = build_tfidf_matrix(["one two three four", "one two purple green"])
    assert find_top_similar(a) == find_top_similar(b)


def test_score_ranking_matches_cosine_order():
    import numpy as np

    from sklearn.metrics.pairwise import cosine_similarity

    matrix = build_tfidf_matrix(CORPUS)
    dense = cosine_similarity(matrix)
    triples = find_top_similar(matrix, top_k=2)
    for i, j, score in triples:
        assert np.isclose(score, dense[i, j])