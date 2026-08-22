import pytest
from sqlalchemy import text

from app.services.embeddings import HashingFakeProvider, paper_text, vector_literal
from scripts.backfill_embeddings import run_backfill


def test_paper_text_joins_and_skips_empty():
    assert paper_text("A Title", "An abstract") == "A Title An abstract"
    assert paper_text("A Title", None) == "A Title"
    assert paper_text("   ", "") == ""
    assert paper_text(None, None) == ""


def test_vector_literal_formatting():
    literal = vector_literal([0.5, -1.0, 1e-07])
    assert literal == "[0.5,-1,1e-07]"


def test_run_backfill_embeds_each_missing_paper_once(session):
    from sqlalchemy import func

    from tests.helpers import add_paper

    add_paper(session, "Alpha vision paper", abstract="convolutional neural networks")
    add_paper(session, "Beta language paper", abstract="transformer attention models")
    empty = add_paper(session, "", abstract=None)  # no usable text: skipped forever
    session.commit()

    embedded, remaining = run_backfill(session, HashingFakeProvider(dim=8))

    assert embedded == 2
    assert remaining == 0
    count, = session.execute(
        text("SELECT count(*) FROM paper_embedding")
    ).fetchone()
    assert count == 2

    # second run is a no-op
    embedded_again, remaining_again = run_backfill(session, HashingFakeProvider(dim=8))
    assert embedded_again == 0
    assert remaining_again == 0

    stored_ids = {
        row[0]
        for row in session.execute(text("SELECT paper_id FROM paper_embedding"))
    }
    assert empty.id not in stored_ids
