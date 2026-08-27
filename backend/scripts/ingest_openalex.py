#!/usr/bin/env python3
"""Idempotent OpenAlex ingestion for Research Radar.

Usage:
    python -m scripts.ingest_openalex [--only-if-empty]
                                      [--boot] [--no-verify-dois]
                                      [--incremental] [--since YYYY-MM-DD]

Modes:
    default          fetch + upsert papers, embed touched papers (O(Δ))
    --only-if-empty  skip ingestion when the paper table already has rows
    --incremental    fetch only works changed since each topic's watermark
                     (requires a prior full ingest); combine with --since
                     YYYY-MM-DD to backfill from an explicit date
    --boot           self-heal: full ingest when empty, else skip (embeddings
                     need no snapshot rebuild).

Exit code 0 on success, 1 on failure.
"""

from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy import func, select

from app.core.settings import get_settings
from app.db.session import SessionLocal
from app.models import Paper
from app.services.ingest import (
    backfill_watermarks,
    resolve_boot_action,
    run_incremental_ingest,
    run_ingest,
)
from app.services.openalex import OpenAlexClient
from app.services.embeddings import FastEmbedProvider

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ingest")


def _topics(settings) -> list[tuple[str, str, str]]:
    return [
        ("computer-vision", settings.openalex_topic_cv_id, "Computer Vision"),
        ("large-language-models", settings.openalex_topic_llm_id, "Large Language Models"),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest papers from OpenAlex")
    parser.add_argument(
        "--only-if-empty",
        action="store_true",
        help="skip ingestion when the paper table already has rows",
    )
    parser.add_argument(
        "--boot",
        action="store_true",
        help="self-heal mode: ingest when empty, else skip",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="fetch only works changed since each topic's last watermark",
    )
    parser.add_argument(
        "--since",
        metavar="YYYY-MM-DD",
        default=None,
        help="with --incremental: fetch changes since this date instead of the watermark",
    )
    parser.add_argument(
        "--no-verify-dois",
        action="store_true",
        help="skip DOI verification at ingest (default: verify, arXiv-first fallback)",
    )
    args = parser.parse_args()

    if args.incremental and args.boot:
        parser.error("--incremental cannot be combined with --boot")
    if args.since and not args.incremental:
        parser.error("--since requires --incremental")

    settings = get_settings()
    topics = _topics(settings)
    embedding_provider = (
        FastEmbedProvider(settings.embedding_model_name)
        if settings.similarity_backend == "embeddings"
        else None
    )

    try:
        with SessionLocal() as session:
            if args.boot:
                papers_count = session.scalar(select(func.count()).select_from(Paper)) or 0
                action = resolve_boot_action(papers_count, 0)
                backfill_watermarks(session, topics)
                if action == "skip":
                    logger.info("boot: papers present (%s), skipping", papers_count)
                    return 0
                logger.info("boot: database empty, running full ingest")

            if args.incremental:
                client = OpenAlexClient(settings.openalex_mailto)
                try:
                    report = run_incremental_ingest(
                        session,
                        client,
                        topics,
                        verify_dois=not args.no_verify_dois,
                        since_date=args.since,
                        embedding_provider=embedding_provider,
                    )
                finally:
                    client.close()
            else:
                client = OpenAlexClient(settings.openalex_mailto)
                try:
                    with SessionLocal() as session:
                        report = run_ingest(
                            session,
                            client,
                            topics,
                            only_if_empty=args.only_if_empty,
                            verify_dois=not args.no_verify_dois,
                            embedding_provider=embedding_provider,
                        )
                finally:
                    client.close()
            logger.info(
                "fetched=%s papers=%s new=%s updated=%s authors=%s relations=%s "
                "dois_checked=%s dois_replaced=%s dois_dropped=%s embedded=%s total_in_db=%s",
                sum(report.topics_fetched.values()),
                report.papers,
                report.papers_new,
                report.papers_updated,
                report.authors,
                report.relations,
                report.dois_checked,
                report.dois_replaced,
                report.dois_dropped,
                report.embedded,
                report.papers_in_db,
            )
            if report.papers > 0:
                logger.info(
                    "by topic: %s",
                    ", ".join(f"{k}={v}" for k, v in report.topics_fetched.items()),
                )
            return 0
    except Exception as exc:
        logger.error("ingestion failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
