from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PaperSimilarity(Base):
    __tablename__ = "paper_similarity"
    __table_args__ = (
        Index(
            "ix_paper_similarity_paper_id_score",
            "paper_id",
            "similarity_score",
        ),
    )

    paper_id: Mapped[int] = mapped_column(
        ForeignKey("paper.id", ondelete="CASCADE"), primary_key=True
    )
    similar_paper_id: Mapped[int] = mapped_column(
        ForeignKey("paper.id", ondelete="CASCADE"), primary_key=True
    )
    similarity_score: Mapped[float] = mapped_column(nullable=False)
