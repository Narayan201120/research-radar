#!/usr/bin/env python3
"""One-shot embedding backfill for papers missing vectors.

Usage:
    python -m scripts.backfill_embeddings [--batch-size N] [--provider fastembed|fake]

Embeds ``title + abstract`` for every paper that has no row in
``paper_embedding`` and at least some usable text; papers whose text is
empty after trimming are skipped permanently (same rule as the TF-IDF
snapshot: no text means nothing to compare). Safe to re-run — already
embedded papers are never touched.
"""

from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy import text

from app.core.settings import get_settings
from app.db.session import SessionLocal
from app.services.embeddings import EmbeddingProvider, FastEmbedProvider, HashingFakeProvider

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("backfill")

_MISSING_TEXT_SQL = "trim(coalesce(p.title, '') || ' ' || coalesce(p.abstract, '')) <> ''"


def _select_batch_sql() -> str:
    return f"""
        SELECT p.id, p.title, p.abstract
        FROM paper p
        LEFT JOIN paper_embedding pe ON pe.paper_id = p.id
        WHERE pe.paper_id IS NULL AND {_MISSING_TEXT_SQL}
        ORDER BY p.id
        LIMIT :limit
    """


def _count_missing_sql() -> str:
    return f"""
        SELECT count(*)
        FROM paper p
        WHERE NOT EXISTS (SELECT 1 FROM paper_embedding pe WHERE pe.paper_id = p.id)
          AND {_MISSING_TEXT_SQL}
    """


def _paper_text(title: str | None, abstract: str | None) -> str:
    parts = [part.strip() for part in (title, abstract) if part and part.strip()]
    return " ".join(parts)


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{component:.7g}" for component in vector) + "]"


def run_backfill(
    session,
    provider: EmbeddingProvider,
    *,
    batch_size: int = 64,
) -> tuple[int, int]:
    """Embed papers lacking vectors. Returns (embedded_now, still_missing)."""
    embedded_total = 0
    while True:
        rows = session.execute(text(_select_batch_sql()), {"limit": batch_size}).all()
        if not rows:
            break
        vectors = provider.embed_texts([_paper_text(r.title, r.abstract) for r in rows])
        for row, vector in zip(rows, vectors):
            session.execute(
                text(
                    "INSERT INTO paper_embedding (paper_id, embedding) "
                    "VALUES (:pid, :emb) ON CONFLICT (paper_id) DO NOTHING"
                ),
                {"pid": row.id, "emb": _vector_literal(vector)},
            )
        session.commit()
        embedded_total += len(rows)
        logger.info("embedded %s papers (%s this batch)", embedded_total, len(rows))

    still_missing = session.execute(text(_count_missing_sql())).scalar_one()
    return embedded_total, int(still_missing)


def main() -> int:
    parser = argparse.ArgumentParser(description="Embed papers that lack vectors")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument(
        "--provider",
        choices=["fastembed", "fake"],
        default="fastembed",
        help="fake uses deterministic hash vectors (offline testing only)",
    )
    args = parser.parse_args()

    provider: EmbeddingProvider
    if args.provider == "fake":
        provider = HashingFakeProvider()
    else:
        provider = FastEmbedProvider(get_settings().embedding_model_name)

    try:
        with SessionLocal() as session:
            missing_before = session.execute(text(_count_missing_sql())).scalar_one()
            logger.info("papers without embeddings: %s", missing_before)
            embedded, remaining = run_backfill(session, provider, batch_size=args.batch_size)
        logger.info(
            "backfill complete: embedded %s, skipped-or-remaining %s",
            embedded,
            remaining,
        )
        return 0
    except Exception as exc:
        logger.error("backfill failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
