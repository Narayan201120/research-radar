"""add ingest_state watermark table

Revision ID: e4a9f2c81b7d
Revises: b0331e8365c3
Create Date: 2026-08-22 08:10:24.113902

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4a9f2c81b7d'
down_revision: Union[str, None] = 'b0331e8365c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('ingest_state',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('topic_slug', sa.String(length=64), nullable=False),
    sa.Column('last_full_ingest_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_incremental_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('topic_slug')
    )


def downgrade() -> None:
    op.drop_table('ingest_state')
