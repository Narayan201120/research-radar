from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IngestDlq(Base):
    """Minimal dead-letter row for works dropped/skipped during ingest.

    Phase 1: rows are written in the same session as the ingest run (before
    commit) so they survive with the run. Replay is dry-run style via
    ``scripts/retry_dlq.py`` (marks ``retried``, no live refetch).

    Run-level flush/commit errors bubble to the scheduler/CLI which log them;
    they are intentionally NOT captured here to keep hooks non-invasive.
    """

    __tablename__ = "ingest_dlq"
    __table_args__ = (
        Index("ix_ingest_dlq_status", "status"),
        Index("ix_ingest_dlq_openalex_id", "openalex_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    run_type: Mapped[str] = mapped_column(Text, nullable=False)
    topic_slug: Mapped[str | None] = mapped_column(String(64), nullable=True)
    openalex_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="pending", nullable=False)
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
