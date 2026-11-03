"""Add login lockout and IP attempt tracking

Revision ID: b6d2f3a8c4e1
Revises: a3c8e1f4b2d6
Create Date: 2026-11-03 21:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = 'b6d2f3a8c4e1'
down_revision = 'a3c8e1f4b2d6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('login_locked_until', sa.DateTime(), nullable=True))

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('failed_login_attempts', server_default=None)

    op.create_table(
        'login_attempt',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=False),
        sa.Column('attempted_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('login_attempt', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_login_attempt_ip_address'), ['ip_address'], unique=False)
        batch_op.create_index(batch_op.f('ix_login_attempt_attempted_at'), ['attempted_at'], unique=False)


def downgrade():
    with op.batch_alter_table('login_attempt', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_login_attempt_attempted_at'))
        batch_op.drop_index(batch_op.f('ix_login_attempt_ip_address'))
    op.drop_table('login_attempt')

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('login_locked_until')
        batch_op.drop_column('failed_login_attempts')
