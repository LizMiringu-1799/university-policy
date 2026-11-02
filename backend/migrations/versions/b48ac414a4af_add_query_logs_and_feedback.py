"""add query_logs and feedback tables

Revision ID: b48ac414a4af
Revises: fbb3c2734411
Create Date: 2026-09-17 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b48ac414a4af'
down_revision = 'fbb3c2734411'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('query_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('session_id', sa.String(length=36), nullable=True),
    sa.Column('document_id', sa.Integer(), nullable=True),
    sa.Column('query_text', sa.Text(), nullable=False),
    sa.Column('status', sa.Enum('answered', 'unanswered', 'error', name='query_log_status'), nullable=False),
    sa.Column('answer_text', sa.Text(), nullable=True),
    sa.Column('confidence', sa.Float(), nullable=True),
    sa.Column('response_ms', sa.Integer(), nullable=True),
    sa.Column('model', sa.String(length=60), nullable=True),
    sa.Column('input_tokens', sa.Integer(), nullable=True),
    sa.Column('output_tokens', sa.Integer(), nullable=True),
    sa.Column('error_code', sa.String(length=40), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('query_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_query_logs_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_query_logs_session_id'), ['session_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_query_logs_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_query_logs_user_id'), ['user_id'], unique=False)

    op.create_table('feedback',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('query_log_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('rating', sa.Enum('up', 'down', name='feedback_rating'), nullable=False),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['query_log_id'], ['query_logs.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('query_log_id')
    )


def downgrade():
    op.drop_table('feedback')

    with op.batch_alter_table('query_logs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_query_logs_user_id'))
        batch_op.drop_index(batch_op.f('ix_query_logs_status'))
        batch_op.drop_index(batch_op.f('ix_query_logs_session_id'))
        batch_op.drop_index(batch_op.f('ix_query_logs_created_at'))

    op.drop_table('query_logs')
