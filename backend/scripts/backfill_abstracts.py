#!/usr/bin/env python3
"""Backfill missing abstracts via Crossref then arXiv.

Usage:
    python -m scripts.backfill_abstracts [--dry-run] [--limit 100]

Fills ``paper.abstract IS NULL`` rows that have a DOI, using the
``abstract_recovery`` waterfall (Crossref JATS → arXiv Atom). Each recovered
paper is re-embedded so BM25 and HNSW see the new text.
"""

from __future__ import annotations

import argparse
import logging

from sqlalchemy import func, select

from app.core.settings import get_settings
from app.db.session import SessionLocal
from app.models import Paper
from app.services.abstract_recovery import recover_missing_abstracts
from app.services.embeddings import FastEmbedProvider

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("backfill_abstracts")


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill missing abstracts")
    parser.add_argument("--dry-run", action="store_true", help="count recoverable without writing")
    parser.add_argument("--limit", type=int, default=1000, help="max papers to attempt (default 1000)")
    parser.add_argument("--batch", type=int, default=20, help="recovery batch size per transaction")
    args = parser.parse_args()

    settings = get_settings()

    with SessionLocal() as session:
        total = session.scalar(select(func.count()).select_from(Paper).where(Paper.abstract.is_(None))) or 0
        recoverable = session.scalar(
            select(func.count()).select_from(Paper).where(Paper.abstract.is_(None), Paper.doi.is_not(None))
        ) or 0
        logger.info("papers with null abstract: %s, recoverable (have doi): %s", total, recoverable)
        if args.dry_run:
            by_source = session.execute(
                select(Paper.abstract_source, func.count()).where(Paper.abstract.is_not(None)).group_by(Paper.abstract_source)
            ).all()
            logger.info("by source: %s", dict(by_source))
            return 0

        embedding_provider = None
        if settings.similarity_backend == "embeddings":
            embedding_provider = FastEmbedProvider(settings.embedding_model_name)

        recovered_total = 0
        remaining = min(args.limit, recoverable)
        while remaining > 0:
            batch = min(args.batch, remaining)
            with SessionLocal() as batch_session:
                recovered = recover_missing_abstracts(
                    batch_session, limit=batch, embedding_provider=embedding_provider
                )
                batch_session.commit()
                recovered_total += recovered
                remaining -= batch
                logger.info("batch %s recovered %s (total %s)", batch, recovered, recovered_total)
                if recovered == 0:
                    break

        logger.info("backfill done: recovered %s / %s attempted", recovered_total, min(args.limit, recoverable))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
