"""add paper_embedding table with hnsw index

Revision ID: d9e4b1c73f28
Revises: c7d3f8a92e14
Create Date: 2026-08-22 12:41:09.220415

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd9e4b1c73f28'
down_revision: Union[str, None] = 'c7d3f8a92e14'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE paper_embedding (
            paper_id INTEGER PRIMARY KEY REFERENCES paper(id) ON DELETE CASCADE,
            embedding vector(384) NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_paper_embedding_hnsw "
        "ON paper_embedding USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS paper_embedding")
