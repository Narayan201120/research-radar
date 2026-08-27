"""add bm25 search index on paper

Revision ID: f3a9c2d74b18
Revises: d9e4b1c73f28
Create Date: 2026-08-22 15:12:37.884210

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f3a9c2d74b18'
down_revision: Union[str, None] = 'd9e4b1c73f28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pg_search >= 0.25 renamed the access method to `paradedb` (`bm25`
    # remains a deprecated alias). key_field must be first and UNIQUE;
    # only one ParadeDB index is permitted per table.
    op.execute(
        "CREATE INDEX paper_search_idx ON paper "
        "USING paradedb (id, title, abstract) "
        "WITH (key_field='id')"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS paper_search_idx")
