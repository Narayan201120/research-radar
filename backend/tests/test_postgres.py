"""Postgres/ParadeDB integration gate — BM25 ranking + ANN similarity.

These tests require a live ``paradedb/paradedb:0.25.3-pg16`` instance with
``DATABASE_URL`` pointing to it. They are marked ``@pytest.mark.postgres`` and
skip gracefully when Docker is not up — hermetic SQLite suite stays green.

Run locally with the stack up:

    DATABASE_URL=postgresql+psycopg://research:research@localhost:5432/research_radar \
        python -m pytest -m postgres -q

In CI the ``services: postgres: paradedb`` provides the DB, so both suites run.
"""

import pytest

from app.services.embeddings import HashingFakeProvider, embed_papers_by_ids
from tests.helpers import add_author, add_paper, add_topic


pytestmark = pytest.mark.postgres


def _seed_small(pg_session):
    """Three papers where TF differs from publication_year ordering."""
    cv = add_topic(pg_session, "computer-vision")
    nlp = add_topic(pg_session, "large-language-models")
    ada = add_author(pg_session, "Ada Lovelace")

    # High-TF but older — should rank first under BM25, last under year-desc.
    high = add_paper(
        pg_session,
        "attention attention attention deep learning",
        abstract="attention attention attention mechanisms transformers",
        year=2023,
        authors=[ada],
        topics=[nlp],
    )
    # Single occurrence, newest — first under ILIKE/year, not under BM25.
    low_new = add_paper(
        pg_session,
        "attention is useful",
        abstract="a single mention of attention",
        year=2025,
        authors=[ada],
        topics=[nlp],
    )
    # Single occurrence, middle year.
    mid = add_paper(
        pg_session,
        "image classification with attention",
        abstract="convolutional networks with attention",
        year=2024,
        authors=[ada],
        topics=[cv],
    )
    pg_session.commit()
    return {"high": high, "low_new": low_new, "mid": mid, "cv": cv, "nlp": nlp, "ada": ada}


def test_ranked_bm25_orders_by_relevance_not_year(pg_client, pg_session):
    data = _seed_small(pg_session)

    legacy = pg_client.get("/papers?q=attention").json()
    assert legacy["total"] == 3
    # year DESC, id DESC — low_new (2025) first
    assert legacy["items"][0]["id"] == data["low_new"].id

    ranked = pg_client.get("/papers?q=attention&ranked=true").json()
    assert ranked["total"] == 3
    # BM25 score DESC — high-TF doc first despite being oldest
    assert ranked["items"][0]["id"] == data["high"].id
    # ordering must differ from legacy
    assert [item["id"] for item in ranked["items"]] != [item["id"] for item in legacy["items"]]


def test_ranked_bm25_and_filters_combine(pg_client, pg_session):
    data = _seed_small(pg_session)
    # year filter ANDs with BM25
    by_year = pg_client.get("/papers?q=attention&ranked=true&year=2024").json()
    assert by_year["total"] == 1
    assert by_year["items"][0]["id"] == data["mid"].id

    # topic filter ANDs with BM25
    by_topic = pg_client.get(f"/papers?q=attention&ranked=true&topic={data['nlp'].slug}").json()
    assert by_topic["total"] == 2
    assert {item["id"] for item in by_topic["items"]} == {data["high"].id, data["low_new"].id}

    # author substring filter ANDs with BM25
    by_author = pg_client.get("/papers?q=attention&ranked=true&author=ada").json()
    assert by_author["total"] == 3


def test_ranked_bm25_pagination_deterministic(pg_client, pg_session):
    _seed_small(pg_session)
    p1 = pg_client.get("/papers?q=attention&ranked=true&page=1&page_size=1").json()
    p2 = pg_client.get("/papers?q=attention&ranked=true&page=2&page_size=1").json()
    p3 = pg_client.get("/papers?q=attention&ranked=true&page=3&page_size=1").json()
    assert len(p1["items"]) == 1 and len(p2["items"]) == 1 and len(p3["items"]) == 1
    assert len({p1["items"][0]["id"], p2["items"][0]["id"], p3["items"][0]["id"]}) == 3
    # stable on repeat
    again = pg_client.get("/papers?q=attention&ranked=true&page=1&page_size=1").json()
    assert again["items"][0]["id"] == p1["items"][0]["id"]
    assert p1["total"] == 3 and p2["total"] == 3


def test_hybrid_fuses_bm25_and_vector(pg_client, pg_session):
    from app.services.embeddings import FastEmbedProvider

    data = _seed_small(pg_session)
    # embed the three small papers so dense side has vectors
    provider = FastEmbedProvider()
    embed_papers_by_ids(pg_session, provider, [data["high"].id, data["low_new"].id, data["mid"].id])
    pg_session.commit()

    hybrid = pg_client.get("/papers?q=attention&hybrid=true").json()
    assert hybrid["total"] == 3
    assert len(hybrid["items"]) == 3
    # hybrid order is RRF, not pure BM25 nor pure year
    ranked = pg_client.get("/papers?q=attention&ranked=true").json()
    legacy = pg_client.get("/papers?q=attention").json()
    assert hybrid["items"] != ranked["items"]
    assert hybrid["items"] != legacy["items"]


def test_hybrid_filters_after(pg_client, pg_session):
    from app.services.embeddings import FastEmbedProvider

    data = _seed_small(pg_session)
    provider = FastEmbedProvider()
    embed_papers_by_ids(pg_session, provider, [data["high"].id, data["low_new"].id, data["mid"].id])
    pg_session.commit()

    # filters applied after RRF — year=2024 should keep only mid
    filtered = pg_client.get("/papers?q=attention&hybrid=true&year=2024").json()
    assert filtered["total"] == 1
    assert filtered["items"][0]["id"] == data["mid"].id

    # topic filter
    by_topic = pg_client.get(f"/papers?q=attention&hybrid=true&topic={data['nlp'].slug}").json()
    assert by_topic["total"] == 2


def test_similar_ann_uses_vectors_when_present(pg_client, pg_session):
    cv = add_topic(pg_session, "computer-vision")
    nlp = add_topic(pg_session, "large-language-models")
    ada = add_author(pg_session, "Ada Lovelace")

    a = add_paper(pg_session, "Attention Is All You Need", abstract="transformer attention mechanisms sequence transduction", year=2025, authors=[ada], topics=[nlp])
    b = add_paper(pg_session, "Attention Is All You Need duplicate title", abstract="transformer attention mechanisms sequence transduction", year=2024, authors=[ada], topics=[nlp])
    c = add_paper(pg_session, "Very Deep Convolutional Networks", abstract="depth of convolutional network improves image classification", year=2023, authors=[ada], topics=[cv])
    pg_session.commit()

    # without vectors — empty (snapshot dropped in a1b2c3d4e5f6)
    assert pg_client.get(f"/papers/{a.id}/similar").json() == []

    # embed all three — ANN should now serve b as nearest (identical text => near-1.0 cosine)
    provider = HashingFakeProvider()
    embed_papers_by_ids(pg_session, provider, [a.id, b.id, c.id])
    pg_session.commit()

    ann = pg_client.get(f"/papers/{a.id}/similar").json()
    # b shares identical title+abstract text => should be top neighbor ahead of c
    assert len(ann) >= 1
    assert ann[0]["id"] == b.id
    assert ann[0]["similarity_score"] > 0


def test_similar_returns_empty_when_vector_absent(pg_client, pg_session):
    cv = add_topic(pg_session, "computer-vision")
    ada = add_author(pg_session, "Ada Lovelace")
    a = add_paper(pg_session, "Paper A", abstract="abstract a", year=2024, authors=[ada], topics=[cv])
    b = add_paper(pg_session, "Paper B", abstract="abstract b", year=2023, authors=[ada], topics=[cv])
    pg_session.commit()
    # no vectors stored — empty post cutover (no snapshot fallback)
    assert pg_client.get(f"/papers/{a.id}/similar").json() == []
    assert pg_client.get(f"/papers/{b.id}/similar").json() == []
