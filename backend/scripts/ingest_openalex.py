#!/usr/bin/env python3
"""Idempotent OpenAlex ingestion for Research Radar.

Usage:
    python -m scripts.ingest_openalex [--only-if-empty]

Exit code 0 on success, 1 on failure.
"""

from __future__ import annotations

import argparse
import logging
import sys

from app.core.settings import get_settings
from app.db.session import SessionLocal
from app.services.ingest import run_ingest
from app.services.openalex import OpenAlexClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ingest")


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest papers from OpenAlex")
    parser.add_argument(
        "--only-if-empty",
        action="store_true",
        help="skip ingestion when the paper table already has rows",
    )
    args = parser.parse_args()

    settings = get_settings()
    topics = [
        ("computer-vision", settings.openalex_topic_cv_id, "Computer Vision"),
        ("large-language-models", settings.openalex_topic_llm_id, "Large Language Models"),
    ]

    client = OpenAlexClient(settings.openalex_mailto)
    try:
        with SessionLocal() as session:
            report = run_ingest(
                session,
                client,
                topics,
                only_if_empty=args.only_if_empty,
            )
        logger.info(
            "fetched=%s papers=%s new=%s updated=%s authors=%s relations=%s total_in_db=%s",
            sum(report.topics_fetched.values()),
            report.papers,
            report.papers_new,
            report.papers_updated,
            report.authors,
            report.relations,
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
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())