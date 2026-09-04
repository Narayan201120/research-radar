#!/usr/bin/env python3
"""Phase-1 DLQ replay (dry-run style, hermetic-safe: no live HTTP).

Usage:
    python -m scripts.retry_dlq [--limit 20] [--topic slug]

Queries ``pending`` ingest_dlq rows oldest-first, logs what would be retried,
then marks each ``retried`` with ``attempts + 1``. No refetch is attempted in
this phase to avoid scope creep; full replay comes later.
"""

from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import IngestDlq

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("retry_dlq")


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run retry of pending ingest DLQ rows")
    parser.add_argument("--limit", type=int, default=20, help="max rows to process")
    parser.add_argument("--topic", default=None, help="only rows for this topic slug")
    args = parser.parse_args()

    with SessionLocal() as session:
        stmt = (
            select(IngestDlq)
            .where(IngestDlq.status == "pending")
            .order_by(IngestDlq.created_at)
            .limit(args.limit)
        )
        if args.topic:
            stmt = stmt.where(IngestDlq.topic_slug == args.topic)
        rows = list(session.scalars(stmt))

        for row in rows:
            logger.info(
                "would-retry dlq id=%s reason=%s openalex_id=%s doi=%s topic=%s attempts=%s",
                row.id,
                row.reason,
                row.openalex_id,
                row.doi,
                row.topic_slug,
                row.attempts,
            )
            row.status = "retried"
            row.attempts = (row.attempts or 0) + 1
        session.commit()

    print(f"processed={len(rows)} marked_retried={len(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
