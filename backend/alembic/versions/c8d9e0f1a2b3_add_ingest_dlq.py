"""add ingest_dlq table

Revision ID: c8d9e0f1a2b3
Revises: b2c3d4e5f6a7
Create Date: 2026-09-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8d9e0f1a2b3'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('ingest_dlq',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('run_type', sa.Text(), nullable=False),
    sa.Column('topic_slug', sa.String(length=64), nullable=True),
    sa.Column('openalex_id', sa.String(length=64), nullable=True),
    sa.Column('doi', sa.String(length=255), nullable=True),
    sa.Column('title', sa.Text(), nullable=True),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('error_detail', sa.Text(), nullable=True),
    sa.Column('attempts', sa.Integer(), server_default='1', nullable=False),
    sa.Column('status', sa.Text(), server_default='pending', nullable=False),
    sa.Column('payload_json', sa.JSON(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ingest_dlq_status', 'ingest_dlq', ['status'], unique=False)
    op.create_index('ix_ingest_dlq_openalex_id', 'ingest_dlq', ['openalex_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_ingest_dlq_openalex_id', table_name='ingest_dlq')
    op.drop_index('ix_ingest_dlq_status', table_name='ingest_dlq')
    op.drop_table('ingest_dlq')
