#!/usr/bin/env python3
"""Deterministic fixture seeder for search-eval CI.

Seeds ~12 fixed papers (``openalex_id`` ``EVAL-01``..``EVAL-12``) covering the
substrate ``tests/fixtures/qrels.jsonl`` queries: attention / transformer /
object-detection / llm-survey / convolutional / sequence-transduction, years
including 2025, all attributed to Ada Lovelace. Vectors are embedded with
:class:`~app.services.embeddings.FastEmbedProvider` (same as
``tests/test_postgres.py`` hybrid tests) via
:func:`~app.services.embeddings.embed_papers_by_ids`.

Idempotency: papers are keyed by the ``EVAL-*`` sentinel prefix, which never
collides with live OpenAlex corpora. Re-runs insert only missing ``EVAL-*``
ids and backfill vectors for any that lack them, so seeding twice is a no-op
beyond verification. Cleanup of live pollution is one statement::

    DELETE FROM paper WHERE openalex_id LIKE 'EVAL-%';

Usage:
    python -m scripts.seed_eval [--drop-first]

``--drop-first`` (default false) truncates ``paper`` first — CI runs on a
fresh service DB so the default path just seeds.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow both `python -m scripts.seed_eval` and `python scripts/seed_eval.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select, text  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.models import Author, Paper, Topic  # noqa: E402
from app.services.embeddings import FastEmbedProvider, embed_papers_by_ids  # noqa: E402
from tests.helpers import add_author, add_paper, add_topic  # noqa: E402

EVAL_PREFIX = "EVAL-"
N_EVAL_PAPERS = 12
LOVELACE = "Ada Lovelace"

# (openalex_suffix, title, abstract, year, topic_slugs)
FIXTURES: list[tuple[str, str, str, int, list[str]]] = [
    ("EVAL-01", "attention attention attention deep learning",
     "attention attention attention mechanisms transformers", 2023, ["large-language-models"]),
    ("EVAL-02", "attention is useful",
     "a single mention of attention in this study", 2025, ["large-language-models"]),
    ("EVAL-03", "image classification with attention",
     "convolutional networks with attention for image classification", 2024,
     ["computer-vision"]),
    ("EVAL-04", "Attention Is All You Need",
     "transformer attention mechanisms for sequence transduction", 2017,
     ["large-language-models"]),
    ("EVAL-05", "A survey of transformer language models",
     "large language model survey covering llama and bert", 2024, ["large-language-models"]),
    ("EVAL-06", "YOLO object detection with transformers",
     "real-time object detection with yolo and detection transformers", 2023,
     ["object-detection"]),
    ("EVAL-07", "Deep residual learning for image recognition",
     "convolutional image classification with residual networks", 2016, ["computer-vision"]),
    ("EVAL-08", "Sequence to sequence transduction with attention",
     "neural sequence transduction with attention over the input sequence", 2025,
     ["large-language-models"]),
    ("EVAL-09", "LLaMA open large language models",
     "llama release: an open large language model family", 2023, ["large-language-models"]),
    ("EVAL-10", "Very deep convolutional networks for large-scale recognition",
     "depth of convolutional network improves image classification accuracy", 2015,
     ["computer-vision"]),
    ("EVAL-11", "Object detection at scale",
     "object detection benchmark comparing yolo variants for detection speed", 2024,
     ["object-detection"]),
    ("EVAL-12", "A survey of large language models",
     "survey of large language models from bert to llama", 2025, ["large-language-models"]),
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Seed deterministic EVAL-* eval fixtures (idempotent).")
    ap.add_argument(
        "--drop-first",
        action="store_true",
        default=False,
        help="TRUNCATE paper first (CI runs on a fresh service DB so the default path just seeds)",
    )
    return ap.parse_args(argv)


def drop_papers(session) -> None:
    """Remove all papers (FK-safe): TRUNCATE ... CASCADE on postgres, ordered DELETEs elsewhere."""
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        session.execute(text("TRUNCATE TABLE paper RESTART IDENTITY CASCADE"))
    else:  # sqlite / other — no TRUNCATE; delete children before parents
        session.execute(text("DELETE FROM paper_embedding"))
        session.execute(text("DELETE FROM paper_author"))
        session.execute(text("DELETE FROM paper_topic"))
        session.execute(text("DELETE FROM paper"))
    session.commit()


def seed(session) -> tuple[int, int]:
    """Insert missing EVAL-* fixtures. Returns (already_present, inserted_now)."""
    # Reuse existing topics/authors when present (idempotent re-runs), else create.
    topic_by_slug = {}
    for slug in ("computer-vision", "large-language-models", "object-detection"):
        existing = session.execute(select(Topic).where(Topic.slug == slug)).scalar_one_or_none()
        topic_by_slug[slug] = existing or add_topic(session, slug)
    session.flush()

    lovelace = session.execute(select(Author).where(Author.name == LOVELACE)).scalar_one_or_none()
    if lovelace is None:
        lovelace = add_author(session, LOVELACE)
    session.flush()

    already = inserted = 0
    for openalex_id, title, abstract, year, slugs in FIXTURES:
        exists = session.execute(select(Paper.id).where(Paper.openalex_id == openalex_id)).scalar_one_or_none()
        if exists is not None:
            already += 1
            continue
        add_paper(
            session,
            title,
            openalex_id=openalex_id,
            abstract=abstract,
            year=year,
            authors=[lovelace],
            topics=[topic_by_slug[s] for s in slugs],
        )
        inserted += 1
    session.commit()
    return already, inserted


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    with SessionLocal() as session:
        if args.drop_first:
            drop_papers(session)
            print("drop-first: truncated paper")
        already, inserted = seed(session)
        ids = session.execute(
            select(Paper.id).where(Paper.openalex_id.like(f"{EVAL_PREFIX}%"))
        ).scalars().all()
        provider = FastEmbedProvider()
        embedded = embed_papers_by_ids(session, provider, list(ids))
        session.commit()
        total = session.execute(
            select(func.count()).select_from(Paper).where(Paper.openalex_id.like(f"{EVAL_PREFIX}%"))
        ).scalar_one()
    print(f"eval papers present: {total} (already present: {already}, inserted: {inserted})")
    print(f"embedded now: {embedded}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
