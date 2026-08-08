"""add index columns to document_versions

Revision ID: a17c4b92e5d1
Revises: e6d298fcd405
Create Date: 2026-08-08 00:00:00.000000

Objective 2 (RAG). Existing rows land on the 'pending' default, so the ingestion
worker's startup recovery picks up the already-uploaded corpus with no separate
backfill step. See docs/design-rag.md §4.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a17c4b92e5d1'
down_revision = 'e6d298fcd405'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'document_versions',
        sa.Column(
            'index_status',
            sa.Enum('pending', 'indexing', 'indexed', 'failed', name='version_index_status'),
            nullable=False,
            server_default='pending',
        ),
    )
    op.add_column('document_versions', sa.Column('chunk_count', sa.Integer(), nullable=True))
    op.add_column('document_versions', sa.Column('index_error', sa.String(length=500), nullable=True))
    op.create_index(
        op.f('ix_document_versions_index_status'), 'document_versions', ['index_status'], unique=False
    )


def downgrade():
    op.drop_index(op.f('ix_document_versions_index_status'), table_name='document_versions')
    op.drop_column('document_versions', 'index_error')
    op.drop_column('document_versions', 'chunk_count')
    op.drop_column('document_versions', 'index_status')
