from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PaperAuthor(Base):
    __tablename__ = "paper_author"
    __table_args__ = (Index("ix_paper_author_author_id", "author_id"),)

    paper_id: Mapped[int] = mapped_column(
        ForeignKey("paper.id", ondelete="CASCADE"), primary_key=True
    )
    author_id: Mapped[int] = mapped_column(
        ForeignKey("author.id", ondelete="CASCADE"), primary_key=True
    )


class PaperTopic(Base):
    __tablename__ = "paper_topic"
    __table_args__ = (Index("ix_paper_topic_topic_id", "topic_id"),)

    paper_id: Mapped[int] = mapped_column(
        ForeignKey("paper.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topic.id", ondelete="CASCADE"), primary_key=True
    )
