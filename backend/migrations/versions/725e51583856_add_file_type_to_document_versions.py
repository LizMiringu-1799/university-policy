"""add file_type to document_versions

Revision ID: 725e51583856
Revises: 22d6f7e50149
Create Date: 2026-09-22 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '725e51583856'
down_revision = '22d6f7e50149'
branch_labels = None
depends_on = None


def upgrade():
    # server_default backfills every existing row as 'pdf', which is what they all are.
    with op.batch_alter_table('document_versions', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('file_type', sa.String(length=10), nullable=False, server_default='pdf')
        )


def downgrade():
    with op.batch_alter_table('document_versions', schema=None) as batch_op:
        batch_op.drop_column('file_type')
