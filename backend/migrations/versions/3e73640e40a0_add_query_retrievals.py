"""add query_retrievals

Revision ID: 3e73640e40a0
Revises: 725e51583856
Create Date: 2026-10-09 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3e73640e40a0'
down_revision = '725e51583856'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('query_retrievals',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('query_log_id', sa.Integer(), nullable=False),
    sa.Column('document_id', sa.Integer(), nullable=False),
    sa.Column('document_version_id', sa.Integer(), nullable=False),
    sa.Column('chunk_id', sa.String(length=80), nullable=False),
    sa.Column('page', sa.Integer(), nullable=True),
    sa.Column('rank', sa.Integer(), nullable=False),
    sa.Column('similarity', sa.Float(), nullable=False),
    sa.Column('cited', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
    sa.ForeignKeyConstraint(['document_version_id'], ['document_versions.id'], ),
    sa.ForeignKeyConstraint(['query_log_id'], ['query_logs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('query_retrievals', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_query_retrievals_document_id'), ['document_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_query_retrievals_query_log_id'), ['query_log_id'], unique=False)


def downgrade():
    with op.batch_alter_table('query_retrievals', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_query_retrievals_query_log_id'))
        batch_op.drop_index(batch_op.f('ix_query_retrievals_document_id'))

    op.drop_table('query_retrievals')
