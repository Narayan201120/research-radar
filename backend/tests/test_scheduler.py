from app.models import IngestState
from app.services.ingest import run_ingest
from scripts.scheduler import run_once
from tests.helpers import make_work
from tests.test_ingest_flow import TOPICS, FakeOpenAlexClient


def test_run_once_absorbs_missing_watermark(session):
    report = run_once(TOPICS, session, FakeOpenAlexClient())
    assert report is None


def test_run_once_returns_report_when_delta_applies(session):
    client = FakeOpenAlexClient()
    run_ingest(session, client, TOPICS)

    client.updates_by_topic = {
        # doi=None keeps the DOI verifier fully offline in this hermetic test
        "T10531": [make_work("W-T10531-sched", "a scheduler vision paper", doi=None)],
        "T10181": [],
    }
    report = run_once(TOPICS, session, client)

    assert report is not None
    assert report.papers == 1
    assert report.papers_new == 1


def test_run_once_leaves_watermark_queryable_after_success(session):
    from sqlalchemy import select

    client = FakeOpenAlexClient()
    run_ingest(session, client, TOPICS)
    original = {
        s.topic_slug: s.last_incremental_at
        for s in session.scalars(select(IngestState)).all()
    }

    client.updates_by_topic = {"T10531": [], "T10181": []}
    run_once(TOPICS, session, client)

    session.expire_all()
    after = {
        s.topic_slug: s.last_incremental_at
        for s in session.scalars(select(IngestState)).all()
    }
    assert all(after[slug] > original[slug] for slug in original)
