#!/usr/bin/env python3
"""Scheduler sidecar: run incremental ingestion on a fixed interval.

Usage:
    python -m scripts.scheduler

Runs ``run_incremental_ingest`` immediately at startup (catching up any
churn accumulated while the stack was down), then sleeps
``INGEST_INTERVAL_HOURS`` between runs. Failures are absorbed and logged —
the next cycle retries — so a transient OpenAlex outage never kills the
sidecar. SIGINT/SIGTERM end the loop cleanly.
"""

from __future__ import annotations

import logging
import random
import signal
import sys
import threading

from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.db.session import SessionLocal
from app.services.embeddings import FastEmbedProvider
from app.services.ingest import IngestReport, run_incremental_ingest
from app.services.openalex import OpenAlexClient
from scripts.ingest_openalex import _topics

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("scheduler")

MIN_INTERVAL_SECONDS = 60.0
MAX_JITTER_SECONDS = 30.0

_stop = threading.Event()


def _install_signal_handlers() -> None:
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_args: _stop.set())


def run_once(
    topics: list[tuple[str, str, str]],
    session: Session,
    client: OpenAlexClient,
    embedding_provider=None,
) -> IngestReport | None:
    """One incremental attempt; failures are logged and absorbed."""
    try:
        report = run_incremental_ingest(
            session,
            client,
            topics,
            verify_dois=True,
            embedding_provider=embedding_provider,
        )
    except Exception as exc:
        if isinstance(exc, RuntimeError) and "watermark" in str(exc).lower():
            logger.error(
                "incremental run failed: missing watermark configuration "
                "(will retry, run full ingest to seed): %s",
                exc,
            )
        else:
            logger.error("incremental run failed: %s", exc)
        return None
    logger.info(
        "incremental ok: %s changed (%s new, %s updated), papers in db=%s",
        report.papers,
        report.papers_new,
        report.papers_updated,
        report.papers_in_db,
    )
    return report


def main() -> int:
    settings = get_settings()
    interval_seconds = max(MIN_INTERVAL_SECONDS, settings.ingest_interval_hours * 3600.0)
    retry_seconds = max(MIN_INTERVAL_SECONDS, settings.scheduler_retry_minutes * 60.0)
    backoff_max_seconds = max(
        MIN_INTERVAL_SECONDS, settings.scheduler_backoff_max_minutes * 60.0
    )
    topics = _topics(settings)
    embedding_provider = (
        FastEmbedProvider(settings.embedding_model_name)
        if settings.similarity_backend == "embeddings"
        else None
    )

    _install_signal_handlers()
    logger.info(
        "scheduler started: incremental ingest every %.1f h, retry %.1f m on failure (stop with SIGTERM)",
        interval_seconds / 3600.0,
        retry_seconds / 60.0,
    )

    consecutive_failures = 0
    while not _stop.is_set():
        client = OpenAlexClient(settings.openalex_mailto)
        success = False
        try:
            with SessionLocal() as session:
                report = run_once(topics, session, client, embedding_provider)
                success = report is not None
        finally:
            client.close()
        if success:
            consecutive_failures = 0
            sleep_seconds = interval_seconds
            logger.info(
                "sleeping %.1f minutes until next run",
                sleep_seconds / 60.0,
            )
        else:
            consecutive_failures += 1
            capped_exp = min(consecutive_failures, 5)
            backoff_seconds = min(
                retry_seconds * (2**capped_exp), backoff_max_seconds
            )
            jitter_seconds = random.uniform(0, MAX_JITTER_SECONDS)
            sleep_seconds = backoff_seconds + jitter_seconds
            logger.info(
                "sleeping %.1f minutes until next retry (failure %d)",
                sleep_seconds / 60.0,
                consecutive_failures,
            )
        if _stop.wait(timeout=sleep_seconds):
            break

    logger.info("scheduler stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
