"""link escalations to query_logs

Revision ID: 22d6f7e50149
Revises: b48ac414a4af
Create Date: 2026-09-22 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '22d6f7e50149'
down_revision = 'b48ac414a4af'
branch_labels = None
depends_on = None


def upgrade():
    # Nullable: rows created before query logging existed have no exchange to point at.
    with op.batch_alter_table('escalations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('query_log_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_escalations_query_log', 'query_logs', ['query_log_id'], ['id']
        )


def downgrade():
    with op.batch_alter_table('escalations', schema=None) as batch_op:
        batch_op.drop_constraint('fk_escalations_query_log', type_='foreignkey')
        batch_op.drop_column('query_log_id')
