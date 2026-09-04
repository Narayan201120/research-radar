from app.models import IngestDlq
from app.services.ingest import _normalize_fetched


def test_normalize_skip_writes_dlq_row(session):
    fetched = {"cv": [{"id": "https://openalex.org/W1", "display_name": "   ", "doi": "https://doi.org/10.1234/x"}]}
    out = _normalize_fetched(fetched, session=session, run_type="full")
    assert out == {}
    session.flush()
    rows = session.query(IngestDlq).all()
    assert len(rows) == 1
    assert rows[0].reason == "normalize_skip"
    assert rows[0].topic_slug == "cv"
    assert rows[0].status == "pending"


def test_dlq_model_defaults(session):
    row = IngestDlq(run_type="scheduler", reason="openalex_error", error_detail="429 boom")
    session.add(row)
    session.commit()
    assert row.id is not None
    assert row.attempts == 1
    assert row.status == "pending"
