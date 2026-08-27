import pytest
from sqlalchemy import func, select, text

from app.models import IngestState, Paper, Topic
from app.services.embeddings import HashingFakeProvider
from app.services.ingest import (
    backfill_watermarks,
    resolve_boot_action,
    run_incremental_ingest,
    run_ingest,
)
from tests.helpers import add_author, add_paper, add_topic, make_work

TOPICS = [
    ("computer-vision", "T10531", "Computer Vision"),
    ("large-language-models", "T10181", "Large Language Models"),
]

PER_TOPIC = 220


def _works_for(topic_id: str, prefix: str) -> list[dict]:
    works = []
    for i in range(PER_TOPIC):
        works.append(
            make_work(
                f"W-{topic_id}-{i}",
                f"{prefix} paper number {i} on topic {topic_id}",
                year=2023 + (i % 3),
                abstract=(
                    f"abstract about {prefix} and neural approaches number {i} "
                    "transformer attention convolutional"
                ),
                author_names=[f"Author {i % 7}", f"CoAuthor {i % 5}"],
            )
        )
    return works


class FakeOpenAlexClient:
    def __init__(self) -> None:
        self.by_topic = {
            "T10531": _works_for("T10531", "vision"),
            "T10181": _works_for("T10181", "language"),
        }
        self.updates_by_topic: dict[str, list[dict]] = {}

    def fetch_topic_works(self, topic_id: str, from_date: str, max_papers: int) -> list[dict]:
        return self.by_topic[topic_id][:max_papers]

    def fetch_updated_works(self, topic_id: str, from_date: str, max_papers: int) -> list[dict]:
        return self.updates_by_topic.get(topic_id, [])[:max_papers]


def test_ingest_populates_all_tables(session):
    client = FakeOpenAlexClient()
    report = run_ingest(session, client, TOPICS, embedding_provider=HashingFakeProvider(dim=8))

    assert report.papers == 2 * PER_TOPIC
    assert report.papers_new == 2 * PER_TOPIC
    assert report.papers_updated == 0
    assert report.authors == 12  # 7 Author i + 5 CoAuthor i
    assert report.relations > 0
    assert report.embedded == 2 * PER_TOPIC
    assert report.similarity_pairs == 0
    assert report.papers_in_db == 2 * PER_TOPIC
    assert session.execute(text("SELECT count(*) FROM paper_embedding")).scalar_one() == 2 * PER_TOPIC


def test_ingest_is_idempotent(session):
    client = FakeOpenAlexClient()
    first = run_ingest(session, client, TOPICS, embedding_provider=HashingFakeProvider(dim=8))
    second = run_ingest(session, client, TOPICS, embedding_provider=HashingFakeProvider(dim=8))

    assert second.papers_new == 0
    assert second.papers_updated == first.papers
    assert second.relations == 0  # no duplicate junction rows
    assert second.authors == first.authors
    assert second.papers_in_db == first.papers_in_db
    assert second.embedded == 0  # no text changed on second run
    assert session.scalar(select(func.count()).select_from(Paper)) == first.papers


def test_only_if_empty_skips_when_papers_exist(session):
    client = FakeOpenAlexClient()
    first = run_ingest(session, client, TOPICS, embedding_provider=HashingFakeProvider(dim=8))
    skipped = run_ingest(session, client, TOPICS, only_if_empty=True)

    assert skipped.papers == 0
    assert skipped.papers_in_db == first.papers


def test_normalization_drops_empty_titles(session):
    client = FakeOpenAlexClient()
    client.by_topic["T10531"].insert(0, make_work("W-junk", "", abstract="orphan"))
    report = run_ingest(session, client, TOPICS, embedding_provider=HashingFakeProvider(dim=8))
    assert report.papers == 2 * PER_TOPIC  # junk work dropped, others kept
    assert "W-junk" not in {p.openalex_id for p in session.scalars(select(Paper)).all()}


def test_boot_action_resolution():
    assert resolve_boot_action(0, 0) == "ingest"
    assert resolve_boot_action(5, 0) == "skip"
    assert resolve_boot_action(5, 10) == "skip"


def test_backfill_watermarks_upgrades_static_database(session):
    backfill_watermarks(session, TOPICS)
    states = _watermarks(session)
    assert set(states) == {"computer-vision", "large-language-models"}
    assert all(s.last_incremental_at is not None for s in states.values())
    assert all(s.last_full_ingest_at is None for s in states.values())

    # idempotent: a second pass must not duplicate or reset rows
    first_pass = {slug: s.last_incremental_at for slug, s in states.items()}
    backfill_watermarks(session, TOPICS)
    second = _watermarks(session)
    assert {slug: s.last_incremental_at for slug, s in second.items()} == first_pass


def test_topic_upsert_matches_slug(session):
    client = FakeOpenAlexClient()
    run_ingest(session, client, TOPICS, embedding_provider=HashingFakeProvider(dim=8))
    assert {t.slug for t in session.scalars(select(Topic)).all()} == {"computer-vision", "large-language-models"}


def test_ingest_verifies_dois_and_drops_unresolvable(session, monkeypatch):
    import httpx

    client = FakeOpenAlexClient()
    # W-dead-1: dead DOI with working arXiv fallback -> replaced, kept
    client.by_topic["T10531"].insert(
        0,
        make_work(
            "W-dead-1",
            "vision paper with dead DOI and arxiv mirror",
            doi="https://doi.org/10.1/dead1",
        ),
    )
    # W-dead-2: dead DOI, no working fallback -> dropped entirely
    client.by_topic["T10531"].insert(
        0,
        make_work(
            "W-dead-2",
            "vision paper with dead DOI and no mirror",
            doi="https://doi.org/10.1/dead2",
        ),
    )
    # give the dead works an arXiv mirror location so fallback can find it
    for w in client.by_topic["T10531"]:
        if w["id"].endswith("W-dead-1"):
            w["locations"] = [{"landing_page_url": "https://arxiv.org/abs/9999.99999"}]

    def handler(request):
        url = str(request.url)
        if "10.1/dead" in url:
            return httpx.Response(404)
        if "arxiv.org" in url:
            return httpx.Response(200)
        return httpx.Response(200)

    transport = httpx.MockTransport(handler)

    report = run_ingest(session, client, TOPICS, verify_dois=True, doi_transport=transport, embedding_provider=HashingFakeProvider(dim=8))

    assert report.dois_checked == 2 * PER_TOPIC + 2
    assert report.dois_replaced == 1
    assert report.dois_dropped == 1
    assert report.papers == 2 * PER_TOPIC + 1
    in_db = {p.openalex_id for p in session.scalars(select(Paper)).all()}
    assert "W-dead-1" in in_db
    assert "W-dead-2" not in in_db
    replaced = session.scalar(
        select(Paper).where(Paper.openalex_id == "W-dead-1")
    )
    assert replaced.doi == "https://arxiv.org/abs/9999.99999"


# --- incremental ingest ---


def _watermarks(session):
    session.expire_all()
    return {
        s.topic_slug: s
        for s in session.scalars(select(IngestState)).all()
    }


def test_full_ingest_seeds_watermarks(session):
    client = FakeOpenAlexClient()
    run_ingest(session, client, TOPICS, embedding_provider=HashingFakeProvider(dim=8))

    states = _watermarks(session)
    assert set(states) == {"computer-vision", "large-language-models"}
    assert all(s.last_full_ingest_at is not None for s in states.values())
    assert all(s.last_incremental_at is not None for s in states.values())


def test_incremental_requires_watermark(session):
    client = FakeOpenAlexClient()
    with pytest.raises(RuntimeError, match="watermark"):
        run_incremental_ingest(session, client, TOPICS)


def test_incremental_adds_new_and_updates_existing(session):
    client = FakeOpenAlexClient()
    run_ingest(session, client, TOPICS, embedding_provider=HashingFakeProvider(dim=8))
    before_count = session.scalar(select(func.count()).select_from(Paper))

    fresh = make_work(
        "W-T10531-new-1",
        "a freshly published vision paper",
        year=2026,
        abstract="novel vision transformer ideas attention",
    )
    changed = make_work(
        "W-T10181-0",
        "language paper number 0 on topic T10181",
        cited_by_count=999_999,
        abstract="abstract about language and neural approaches number 0 transformer attention convolutional",
    )
    client.updates_by_topic = {"T10531": [fresh], "T10181": [changed]}

    report = run_incremental_ingest(session, client, TOPICS, embedding_provider=HashingFakeProvider(dim=8))

    assert report.topics_fetched == {"computer-vision": 1, "large-language-models": 1}
    assert report.papers == 2
    assert report.papers_new == 1
    assert report.papers_updated == 1
    assert session.scalar(select(func.count()).select_from(Paper)) == before_count + 1

    session.expire_all()
    refreshed = session.scalar(select(Paper).where(Paper.openalex_id == "W-T10181-0"))
    assert refreshed.cited_by_count == 999_999


def test_incremental_advances_watermark(session):
    client = FakeOpenAlexClient()
    run_ingest(session, client, TOPICS, embedding_provider=HashingFakeProvider(dim=8))
    original = {slug: s.last_incremental_at for slug, s in _watermarks(session).items()}

    client.updates_by_topic = {
        "T10531": [make_work("W-T10531-new-2", "another new vision paper")],
        "T10181": [],
    }
    run_incremental_ingest(session, client, TOPICS, embedding_provider=HashingFakeProvider(dim=8))

    after = {slug: s.last_incremental_at for slug, s in _watermarks(session).items()}
    assert all(after[slug] > original[slug] for slug in original)


def test_incremental_is_idempotent(session):
    client = FakeOpenAlexClient()
    run_ingest(session, client, TOPICS, embedding_provider=HashingFakeProvider(dim=8))
    client.updates_by_topic = {
        "T10531": [make_work("W-T10531-inc-1", "an incremental vision paper")],
        "T10181": [],
    }

    first = run_incremental_ingest(session, client, TOPICS, embedding_provider=HashingFakeProvider(dim=8))
    second = run_incremental_ingest(session, client, TOPICS, embedding_provider=HashingFakeProvider(dim=8))

    assert first.papers_new == 1
    assert second.papers_new == 0
    assert second.papers_updated == 1
    assert second.papers_in_db == first.papers_in_db
    assert second.relations == 0


def test_incremental_empty_delta_still_commits_watermark(session):
    client = FakeOpenAlexClient()
    run_ingest(session, client, TOPICS, embedding_provider=HashingFakeProvider(dim=8))
    original = {slug: s.last_incremental_at for slug, s in _watermarks(session).items()}

    client.updates_by_topic = {"T10531": [], "T10181": []}
    report = run_incremental_ingest(session, client, TOPICS, embedding_provider=HashingFakeProvider(dim=8))

    assert report.papers == 0
    assert report.similarity_pairs == 0
    after = {slug: s.last_incremental_at for slug, s in _watermarks(session).items()}
    assert all(after[slug] > original[slug] for slug in original)


def test_incremental_since_overrides_watermark(session):
    client = FakeOpenAlexClient()
    run_ingest(session, client, TOPICS, embedding_provider=HashingFakeProvider(dim=8))

    client.updates_by_topic = {
        "T10531": [make_work("W-T10531-backfill", "a backfilled vision paper")],
        "T10181": [],
    }
    report = run_incremental_ingest(session, client, TOPICS, since_date="2020-01-01", embedding_provider=HashingFakeProvider(dim=8))

    assert report.papers == 1
    assert report.papers_new == 1


def test_cross_topic_duplicate_keeps_both_topics(session):
    """Regression: a work fetched under both topics must belong to both."""
    client = FakeOpenAlexClient()
    shared = make_work(
        "W-shared-1",
        "a paper relevant to both topics",
        year=2024,
        abstract="shared attention text relevant everywhere",
    )
    client.by_topic["T10531"].append(shared)
    client.by_topic["T10181"].append(dict(shared))

    report = run_ingest(session, client, TOPICS, embedding_provider=HashingFakeProvider(dim=8))
    assert report.papers == 2 * PER_TOPIC + 1

    paper = session.scalar(select(Paper).where(Paper.openalex_id == "W-shared-1"))
    assert paper is not None
    assert {t.slug for t in paper.topics} == {"computer-vision", "large-language-models"}


# --- embeddings mode ---


def test_full_ingest_embeds_all_and_skips_snapshot(session):
    client = FakeOpenAlexClient()
    report = run_ingest(
        session,
        client,
        TOPICS,
        embedding_provider=HashingFakeProvider(dim=8),
    )

    assert report.embedded == 2 * PER_TOPIC
    assert report.similarity_pairs == 0
    count = session.execute(text("SELECT count(*) FROM paper_embedding")).scalar_one()
    assert count == 2 * PER_TOPIC


def test_incremental_embeds_only_text_changed_papers(session):
    client = FakeOpenAlexClient()
    run_ingest(session, client, TOPICS, embedding_provider=HashingFakeProvider(dim=8))  # baseline with embeddings

    fresh = make_work("W-T10531-new-9", "a brand new vision paper")
    citation_bump = make_work(
        "W-T10181-3",
        "language paper number 3 on topic T10181",
        cited_by_count=12345,
        abstract=(
            "abstract about language and neural approaches number 3 "
            "transformer attention convolutional"
        ),
    )
    client.updates_by_topic = {"T10531": [fresh], "T10181": [citation_bump]}

    report = run_incremental_ingest(
        session,
        client,
        TOPICS,
        embedding_provider=HashingFakeProvider(dim=8),
    )

    assert report.papers == 2  # both upserted...
    assert report.embedded == 1  # ...but the citation bump alone keeps its vector
