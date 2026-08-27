"""drop paper_similarity snapshot table (tf-idf path retired)

Revision ID: a1b2c3d4e5f6
Revises: f3a9c2d74b18
Create Date: 2026-08-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f3a9c2d74b18'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("paper_similarity")


def downgrade() -> None:
    op.create_table(
        "paper_similarity",
        sa.Column("paper_id", sa.Integer(), nullable=False),
        sa.Column("similar_paper_id", sa.Integer(), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["paper_id"], ["paper.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["similar_paper_id"], ["paper.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("paper_id", "similar_paper_id"),
    )
    op.create_index(
        "ix_paper_similarity_paper_id_score",
        "paper_similarity",
        ["paper_id", "similarity_score"],
    )
