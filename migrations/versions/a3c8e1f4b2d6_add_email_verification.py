"""Add email verification fields

Revision ID: a3c8e1f4b2d6
Revises: 805d2e61136c
Create Date: 2026-11-02 17:33:00

"""
from alembic import op
import sqlalchemy as sa


revision = 'a3c8e1f4b2d6'
down_revision = '805d2e61136c'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email_verified', sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column('otp_hash', sa.String(length=256), nullable=True))
        batch_op.add_column(sa.Column('otp_expires_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('otp_sent_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('otp_resend_count', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('otp_resend_window_start', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('otp_attempts', sa.Integer(), nullable=False, server_default='0'))
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('email_verified', server_default=None)
        batch_op.alter_column('otp_resend_count', server_default=None)
        batch_op.alter_column('otp_attempts', server_default=None)


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('otp_attempts')
        batch_op.drop_column('otp_resend_window_start')
        batch_op.drop_column('otp_resend_count')
        batch_op.drop_column('otp_sent_at')
        batch_op.drop_column('otp_expires_at')
        batch_op.drop_column('otp_hash')
        batch_op.drop_column('email_verified')
