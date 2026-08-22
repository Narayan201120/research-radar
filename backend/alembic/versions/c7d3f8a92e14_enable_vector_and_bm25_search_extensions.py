"""enable vector and bm25 search extensions

Revision ID: c7d3f8a92e14
Revises: e4a9f2c81b7d
Create Date: 2026-08-22 10:02:41.552318

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c7d3f8a92e14'
down_revision: Union[str, None] = 'e4a9f2c81b7d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_search")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS pg_search")
    op.execute("DROP EXTENSION IF EXISTS vector")
