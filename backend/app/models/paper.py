from datetime import datetime

from sqlalchemy import DateTime, Index, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Paper(Base):
    __tablename__ = "paper"
    __table_args__ = (Index("ix_paper_publication_year", "publication_year"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    openalex_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    publication_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cited_by_count: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    authors: Mapped[list["Author"]] = relationship(
        secondary="paper_author", back_populates="papers"
    )
    topics: Mapped[list["Topic"]] = relationship(
        secondary="paper_topic", back_populates="papers"
    )
