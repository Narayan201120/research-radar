from sqlalchemy import func, select

from app.models import Paper, PaperSimilarity, Topic
from app.services.ingest import resolve_boot_action, run_ingest, run_similarity_rebuild
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

    def fetch_topic_works(self, topic_id: str, from_date: str, max_papers: int) -> list[dict]:
        return self.by_topic[topic_id][:max_papers]


def test_ingest_populates_all_tables(session):
    client = FakeOpenAlexClient()
    report = run_ingest(session, client, TOPICS)

    assert report.papers == 2 * PER_TOPIC
    assert report.papers_new == 2 * PER_TOPIC
    assert report.papers_updated == 0
    assert report.authors == 12  # 7 Author i + 5 CoAuthor i
    assert report.relations > 0
    assert report.similarity_pairs == 2 * PER_TOPIC * 5
    assert report.papers_in_db == 2 * PER_TOPIC
    assert session.scalar(select(func.count()).select_from(PaperSimilarity)) == 2 * PER_TOPIC * 5


def test_ingest_is_idempotent(session):
    client = FakeOpenAlexClient()
    first = run_ingest(session, client, TOPICS)
    second = run_ingest(session, client, TOPICS)

    assert second.papers_new == 0
    assert second.papers_updated == first.papers
    assert second.relations == 0  # no duplicate junction rows
    assert second.authors == first.authors
    assert second.papers_in_db == first.papers_in_db
    assert second.similarity_pairs == first.similarity_pairs
    assert session.scalar(select(func.count()).select_from(Paper)) == first.papers


def test_only_if_empty_skips_when_papers_exist(session):
    client = FakeOpenAlexClient()
    first = run_ingest(session, client, TOPICS)
    skipped = run_ingest(session, client, TOPICS, only_if_empty=True)

    assert skipped.papers == 0
    assert skipped.papers_in_db == first.papers


def test_normalization_drops_empty_titles(session):
    client = FakeOpenAlexClient()
    client.by_topic["T10531"].insert(0, make_work("W-junk", "", abstract="orphan"))
    report = run_ingest(session, client, TOPICS)
    assert report.papers == 2 * PER_TOPIC  # junk work dropped, others kept
    assert "W-junk" not in {p.openalex_id for p in session.scalars(select(Paper)).all()}


def test_similarity_rebuild_is_idempotent(session):
    client = FakeOpenAlexClient()
    run_ingest(session, client, TOPICS)
    first = run_similarity_rebuild(session)
    second = run_similarity_rebuild(session)
    assert first == second == 2 * PER_TOPIC * 5


def test_boot_action_resolution():
    assert resolve_boot_action(0, 0) == "ingest"
    assert resolve_boot_action(5, 0) == "rebuild-similarity"
    assert resolve_boot_action(5, 10) == "skip"


def test_boot_rebuild_fixes_missing_similarity(session):
    client = FakeOpenAlexClient()
    run_ingest(session, client, TOPICS)
    session.execute(PaperSimilarity.__table__.delete())
    session.commit()

    assert resolve_boot_action(session.scalar(select(func.count()).select_from(Paper)), 0) == "rebuild-similarity"
    pairs = run_similarity_rebuild(session)
    assert pairs == 2 * PER_TOPIC * 5
    assert resolve_boot_action(
        session.scalar(select(func.count()).select_from(Paper)),
        session.scalar(select(func.count()).select_from(PaperSimilarity)),
    ) == "skip"


def test_topic_upsert_matches_slug(session):
    client = FakeOpenAlexClient()
    run_ingest(session, client, TOPICS)
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

    report = run_ingest(session, client, TOPICS, verify_dois=True, doi_transport=transport)

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