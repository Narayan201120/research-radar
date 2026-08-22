from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IngestState(Base):
    """Per-topic ingestion watermark used by incremental runs.

    ``last_incremental_at`` records when the last delta fetch *started*, so
    works changed during that run are picked up by the next one.
    """

    __tablename__ = "ingest_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    last_full_ingest_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_incremental_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
