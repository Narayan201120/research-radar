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
import signal
import sys
import threading

from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.db.session import SessionLocal
from app.services.ingest import IngestReport, run_incremental_ingest
from app.services.openalex import OpenAlexClient
from scripts.ingest_openalex import _topics

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("scheduler")

MIN_INTERVAL_SECONDS = 60.0

_stop = threading.Event()


def _install_signal_handlers() -> None:
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_args: _stop.set())


def run_once(
    topics: list[tuple[str, str, str]],
    session: Session,
    client: OpenAlexClient,
) -> IngestReport | None:
    """One incremental attempt; failures are logged and absorbed."""
    try:
        report = run_incremental_ingest(session, client, topics, verify_dois=True)
    except Exception as exc:
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
    topics = _topics(settings)

    _install_signal_handlers()
    logger.info(
        "scheduler started: incremental ingest every %.1f h (stop with SIGTERM)",
        interval_seconds / 3600.0,
    )

    while not _stop.is_set():
        client = OpenAlexClient(settings.openalex_mailto)
        try:
            with SessionLocal() as session:
                run_once(topics, session, client)
        finally:
            client.close()
        logger.info("sleeping %.1f minutes until next run", interval_seconds / 60.0)
        if _stop.wait(timeout=interval_seconds):
            break

    logger.info("scheduler stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
